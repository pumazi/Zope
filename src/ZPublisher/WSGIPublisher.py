##############################################################################
#
# Copyright (c) 2002 Zope Foundation and Contributors.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################
""" Python Object Publisher -- Publish Python objects on web servers
"""
from cStringIO import StringIO
import sys
import time

from zExceptions import Redirect
from ZServer.medusa.http_date import build_http_date
from ZPublisher.HTTPResponse import HTTPResponse
from ZPublisher.HTTPRequest import HTTPRequest
from ZPublisher.mapply import mapply
from ZPublisher.Publish import Retry
from ZPublisher.Publish import call_object
from ZPublisher.Publish import dont_publish_class
from ZPublisher.Publish import get_module_info
from ZPublisher.Publish import missing_name

_NOW = None     # overwrite for testing
def _now():
    if _NOW is not None:
        return _NOW
    return time.time()

class WSGIResponse(HTTPResponse):
    """A response object for WSGI

    This Response object knows nothing about ZServer, but tries to be
    compatible with the ZServerHTTPResponse. 
    
    Most significantly, streaming is not (yet) supported.
    """
    _streaming = _chunking = 0
    _http_version = None
    _server_version = None
    _http_connection = None

    # Set this value to 1 if streaming output in
    # HTTP/1.1 should use chunked encoding
    http_chunk = 0
    
    def __str__(self):

        if self._wrote:
            if self._chunking:
                return '0\r\n\r\n'
            else:
                return ''

        headers = self.headers
        body = self.body

        # set 204 (no content) status if 200 and response is empty
        # and not streaming
        if ('content-type' not in headers and 
            'content-length' not in headers and 
            not self._streaming and self.status == 200):
            self.setStatus('nocontent')

        # add content length if not streaming
        content_length = headers.get('content-length')

        if content_length is None and not self._streaming:
            self.setHeader('content-length', len(body))

        chunks = []
        append = chunks.append

        # status header must come first.
        version = self._http_version or '1.0'
        append("HTTP/%s %d %s" % (version, self.status, self.errmsg))

        # add zserver headers
        if self._server_version is not None:
            append('Server: %s' % self._server_version)

        append('Date: %s' % build_http_date(_now()))

        if self._http_version == '1.0':
            if (self._http_connection == 'keep-alive' and 
                'content-length' in self.headers):
                self.setHeader('Connection', 'Keep-Alive')
            else:
                self.setHeader('Connection', 'close')

        # Close the connection if we have been asked to.
        # Use chunking if streaming output.
        if self._http_version == '1.1':
            if self._http_connection == 'close':
                self.setHeader('Connection', 'close')
            elif not self.headers.has_key('content-length'):
                if self.http_chunk and self._streaming:
                    self.setHeader('Transfer-Encoding', 'chunked')
                    self._chunking = 1
                else:
                    self.setHeader('Connection','close')

        for key, val in headers.items():
            if key.lower() == key:
                # only change non-literal header names
                key = '-'.join([x.capitalize() for x in key.split('-')])
            append("%s: %s" % (key, val))

        if self.cookies:
            chunks.extend(self._cookie_list())

        for key, value in self.accumulated_headers:
            append("%s: %s" % (key, value))

        append('') # RFC 2616 mandates empty line between headers and payload
        append(body)

        return "\r\n".join(chunks)

def publish(request, module_name, after_list, debug=0,
            # Optimize:
            call_object=call_object,
            missing_name=missing_name,
            dont_publish_class=dont_publish_class,
            mapply=mapply,
            ):

    (bobo_before, bobo_after, object, realm, debug_mode, err_hook,
     validated_hook, transactions_manager)= get_module_info(module_name)

    parents=None
    response=None
    try:
        request.processInputs()

        request_get=request.get
        response=request.response

        # First check for "cancel" redirect:
        if request_get('SUBMIT','').strip().lower()=='cancel':
            cancel=request_get('CANCEL_ACTION','')
            if cancel:
                raise Redirect, cancel

        after_list[0]=bobo_after
        if debug_mode:
            response.debug_mode=debug_mode
        if realm and not request.get('REMOTE_USER',None):
            response.realm=realm

        if bobo_before is not None:
            bobo_before()

        # Get the path list.
        # According to RFC1738 a trailing space in the path is valid.
        path=request_get('PATH_INFO')

        request['PARENTS']=parents=[object]

        if transactions_manager:
            transactions_manager.begin()

        object=request.traverse(path, validated_hook=validated_hook)

        if transactions_manager:
            transactions_manager.recordMetaData(object, request)

        result=mapply(object, request.args, request,
                      call_object,1,
                      missing_name,
                      dont_publish_class,
                      request, bind=1)

        if result is not response:
            response.setBody(result)

        if transactions_manager:
            transactions_manager.commit()

        return response
    except:

        # DM: provide nicer error message for FTP
        sm = None
        if response is not None:
            sm = getattr(response, "setMessage", None)

        if sm is not None:
            from asyncore import compact_traceback
            cl,val= sys.exc_info()[:2]
            sm('%s: %s %s' % (
                getattr(cl,'__name__',cl), val,
                debug_mode and compact_traceback()[-1] or ''))

        if err_hook is not None:
            if parents:
                parents=parents[0]
            try:
                try:
                    return err_hook(parents, request,
                                    sys.exc_info()[0],
                                    sys.exc_info()[1],
                                    sys.exc_info()[2],
                                    )
                except Retry:
                    if not request.supports_retry():
                        return err_hook(parents, request,
                                        sys.exc_info()[0],
                                        sys.exc_info()[1],
                                        sys.exc_info()[2],
                                        )
            finally:
                if transactions_manager:
                    transactions_manager.abort()

            # Only reachable if Retry is raised and request supports retry.
            newrequest=request.retry()
            request.close()  # Free resources held by the request.
            try:
                return publish(newrequest, module_name, after_list, debug)
            finally:
                newrequest.close()

        else:
            if transactions_manager:
                transactions_manager.abort()
            raise

def publish_module(environ, start_response):

    must_die=0
    status=200
    after_list=[None]
    stdout = StringIO()
    stderr = StringIO()
    response = WSGIResponse(stdout=stdout, stderr=stderr)
    response._http_version = environ['SERVER_PROTOCOL'].split('/')[1]
    response._http_connection = environ.get('CONNECTION_TYPE', 'close')
    response._server_version = environ['SERVER_SOFTWARE']

    request = HTTPRequest(environ['wsgi.input'], environ, response)

    # Let's support post-mortem debugging
    handle_errors = environ.get('wsgi.handleErrors', True)
    
    try:
        response = publish(request, 'Zope2', after_list=[None], 
                           debug=handle_errors)
    except SystemExit, v:
        must_die=sys.exc_info()
        request.response.exception(must_die)
    except ImportError, v:
        if isinstance(v, tuple) and len(v)==3: must_die=v
        elif hasattr(sys, 'exc_info'): must_die=sys.exc_info()
        else: must_die = SystemExit, v, sys.exc_info()[2]
        request.response.exception(1, v)
    except:
        request.response.exception()
        status=response.getStatus()

    if response:
        # Start the WSGI server response
        status = response.getHeader('status')
        # ZServerHTTPResponse calculates all headers and things when you
        # call it's __str__, so we need to get it, and then munge out
        # the headers from it. It's a bit backwards, and we might optimize
        # this by not using ZServerHTTPResponse at all, and making the 
        # HTTPResponses more WSGI friendly. But this works.
        result = str(response)
        headers, body = result.split('\r\n\r\n',1)
        headers = [tuple(n.split(': ',1)) for n in headers.split('\r\n')[1:]]
        start_response(status, headers)
        # If somebody used response.write, that data will be in the
        # stdout StringIO, so we put that before the body.
        # XXX This still needs verification that it really works.
        result=(stdout.getvalue(), body)
    request.close()
    stdout.close()

    if after_list[0] is not None: after_list[0]()
    
    if must_die:
        # Try to turn exception value into an exit code.
        try:
            if hasattr(must_die[1], 'code'):
                code = must_die[1].code
            else: code = int(must_die[1])
        except:
            code = must_die[1] and 1 or 0
        if hasattr(request.response, '_requestShutdown'):
            request.response._requestShutdown(code)

        try: raise must_die[0], must_die[1], must_die[2]
        finally: must_die=None
        
    # Return the result body iterable.
    return result


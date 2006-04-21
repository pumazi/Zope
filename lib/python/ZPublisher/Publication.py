##############################################################################
#
# Copyright (c) 2005 Zope Corporation and Contributors. All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################
__version__='$Revision$'[11:-2]

import re
import sys
import transaction
import types
import xmlrpc

from zope.event import notify
from zope.component import queryUtility, queryMultiAdapter
from zope.interface import implements
from zope.publisher.interfaces import IRequest, IPublication
from zope.publisher.interfaces import NotFound, IPublicationRequest
import zope.publisher.interfaces
from zope.publisher.browser import BrowserRequest
from zope.publisher.browser import BrowserResponse
from zope.publisher.http import StrResult
from zope.app.publication.interfaces import EndRequestEvent
from zope.app.publication.interfaces import BeforeTraverseEvent
from zope.app.publication.interfaces import IBrowserRequestFactory
from zope.app.publication.interfaces import IRequestPublicationFactory
from zope.app.traversing.namespace import nsParse
from zope.app.traversing.namespace import namespaceLookup
from zope.app.traversing.interfaces import TraversalError

from ZPublisher.Publish import Retry
from ZPublisher.Publish import get_module_info, call_object
from ZPublisher.Publish import missing_name, dont_publish_class
from ZPublisher.mapply import mapply
from ZPublisher.BaseRequest import RequestContainer
from ZPublisher.BaseRequest import typeCheck

from ZPublisher.HTTPRequest import HTTPRequest
from ZPublisher.HTTPResponse import HTTPResponse
from cStringIO import StringIO
import traceback
from zope.publisher.http import status_reasons, DirectResult
from zope.publisher.interfaces import IPublisherRequest
from zope import component


_marker = object()

class Zope3HTTPRequestTraverser(object):
    implements(zope.publisher.interfaces.ITraversingRequest)

    def __init__(self, request):
        self.request = request

    def traverse(self, object):
        path = self.request.get('PATH_INFO')
        self.request['PARENTS'] = [object]

        return self.request.traverse(path, self.request.response,
                                     self.request.publication.validated_hook)


class ZopePublication(object):
    """Base Zope2 publication specification.
    """
    implements(IPublication)

    def __init__(self, db = None, module_name = "Zope2"):
        # db is a ZODB.DB.DB object.
        # XXX We don't use this yet.
        self.db = db

        # Published module, bobo-style.
        self.module_name = module_name

        # Fetch module info to be backwards compatible with 'bobo'
        # and Zope 2.
        (self.bobo_before, self.bobo_after,
         self.root, self.realm, self.debug_mode,
         self.err_hook, self.validated_hook,
         self.transactions_manager) = get_module_info(self.module_name)

    def beforeTraversal(self, request):
        # First check for "cancel" redirect:
        if request.get('SUBMIT','').strip().lower()=='cancel':
            # XXX Deprecate this, the Zope 2+3 publication won't support it.
            cancel = request.get('CANCEL_ACTION','')
            if cancel:
                raise Redirect, cancel

        if self.debug_mode:
            request.response.debug_mode = self.debug_mode
        if self.realm and not request.get('REMOTE_USER', None):
            request.response.realm = self.realm

        # First part of old ZPublisher.Publish.publish. Call
        # 'bobo_before' hooks and start a new transaction using the
        # 'transaction_manager'.
        if self.bobo_before is not None:
            self.bobo_before()
        if self.transactions_manager:
            self.transactions_manager.begin()

    def callTraversalHooks(self, request, ob):
        # Call __before_publishing_traverse__ hooks
        bpth = getattr(ob, '__before_publishing_traverse__', None)
        if bpth is not None:
            bpth(ob, request)

        # And then fire an event
        notify(BeforeTraverseEvent(ob, request))

    def afterTraversal(self, request, ob):
        # XXX Authentication should happen here. It used to happen at
        # the end of BaseRequest.traverse().

        # Zope 2 does annotate the transaction just after traversal,
        # but before calling the object. Zope 3 does annotate the
        # transaction on afterCall instead.
        txn = transaction.get()
        self.annotateTransaction(txn, request, ob)

    def getApplication(self, request):
        # Return the application object for the given module.
        ob = self.root

        # Now, some code from ZPublisher.BaseRequest:
        # If the top object has a __bobo_traverse__ method, then use it
        # to possibly traverse to an alternate top-level object.
        try:
            if hasattr(ob, '__bobo_traverse__'):
                ob = ob.__bobo_traverse__(request)
        except:
            pass

        if hasattr(ob, '__of__'):
            # Try to bind the top-level object to the request
            # This is how you get 'self.REQUEST'
            ob = ob.__of__(RequestContainer(REQUEST=request))

        return ob

    def callObject(self, request, ob):
        # Call the object the same way it's done in Zope 2.

        # XXX Check if it's a Zope 3 or a Zope 2 request. Might not be
        # true because someone (Five?) is saying that the Zope 2
        # request implements IPublicationRequest so we check for the
        # method name. Yuck.
        if (IPublicationRequest.providedBy(request) and
            hasattr(request, 'getPositionalArguments')):
            args = request.getPositionalArguments()
        else:
            # It's a Zope 2 request.
            args = request.args
        result = mapply(ob, args,
                        request, call_object, 1, missing_name,
                        dont_publish_class, request, bind=1)
        ## XXX - what the hell is this.
        ## if isinstance(request, Zope2BrowserRequest):
        ##     return StrResult(str(result))
        return result

    def afterCall(self, request, ob):
        # Last part of ZPublisher.Publish.{publish, publish_module_standard},
        # commit the transaction.
        if self.transactions_manager:
            self.transactions_manager.commit()

    def endRequest(self, request, ob):
        # End the request the Zope 3-way, by firing an event.
        notify(EndRequestEvent(ob, request))

    def annotateTransaction(self, txn, request, ob):
        """Set some useful meta-information on the transaction. This
        information is used by the undo framework, for example.

        This method is not part of the `IPublication` interface, since
        it's specific to this particular implementation.
        """
        # Zope 2 uses the 'recordMetadata' method of the transaction
        # manager to record the transaction metadata.
        if self.transactions_manager:
            self.transactions_manager.recordMetaData(ob, request)

    def _abort(self):
        if self.transactions_manager:
            self.transactions_manager.abort()

    def handleException(self, object, request, exc_info, retry_allowed=True):
        if isinstance(object, types.ListType):
            object = object[0]

        # DM: provide nicer error message for FTP
        sm = getattr(request.response, "setMessage", None)
        if sm is not None:
            from asyncore import compact_traceback
            cl,val= sys.exc_info()[:2]
            sm('%s: %s %s' % (
                getattr(cl,'__name__',cl), val,
                debug_mode and compact_traceback()[-1] or ''))

        # Some exception handling from ZPublisher.Publish.publish().
        if self.err_hook is None:
            self._abort()
            raise

        # If an err_hook was registered, use it.
        try:
            try:
                return self.err_hook(object, request,
                                     exc_info[0],
                                     exc_info[1],
                                     exc_info[2],
                                     )
            except Retry, retry_exception:
                if retry_allowed:
                    raise zope.publisher.interfaces.Retry(sys.exc_info)
                return self.err_hook(object, request,
                                     sys.exc_info()[0],
                                     sys.exc_info()[1],
                                     sys.exc_info()[2],
                                     )
            except:
                request.response.exception()
                return request.response
        finally:
            self._abort()

        # XXX After this code, in ZPublisher.Publish.publish(), Zope 2
        # does a 'Retry' if a 'Retry' exception happens and the
        # request supports retry. It's not clear how this will be
        # handled by Zope 3.

    def traverseName(self, request, ob, name):
        nm = name # the name to look up the object with

        if name and name[:1] in '@+':
            # Process URI segment parameters.
            ns, nm = nsParse(name)
            if ns:
                try:
                    ob2 = namespaceLookup(ns, nm, ob, request)
                except TraversalError:
                    raise NotFound(ob, name)

                return ob2.__of__(ob)

        if nm == '.':
            return ob

        if zope.publisher.interfaces.IPublishTraverse.providedBy(ob):
            ob2 = ob.publishTraverse(request, nm)
        else:
            # self is marker
            adapter = queryMultiAdapter((ob, request),
                                     zope.publisher.interfaces.IPublishTraverse,
                                     default = self)
            if adapter is self:
                ## Zope2 doesn't set up its own adapters in a lot of cases
                ## so we will just use a default adapter.
                adapter = Zope2PublishTraverseAdapter(ob, request)

            ob2 = adapter.publishTraverse(request, nm)

        return ob2

    def getDefaultTraversal(self, request, ob):
        if hasattr(ob, '__browser_default__'):
            return object.__browser_default__(request)
        if getattr(ob, 'index_html', None):
            return ob, ['index_html']
        return ob, []

_publications = {}
def get_publication(module_name=None):
    if module_name is None:
        module_name = "Zope2"
    if not _publications.has_key(module_name):
        _publications[module_name] = ZopePublication(db=None,
                                                     module_name=module_name)
    return _publications[module_name]


class Zope2PublishTraverseAdapter(object):
    implements(zope.publisher.interfaces.IPublishTraverse)

    def __init__(self, context, request):
        self.context = context

    def subObject(self, request, ob, name):
        # How did this request come in? (HTTP GET, PUT, POST, etc.)
        method = request.get('REQUEST_METHOD', 'GET').upper()

        if method == 'GET' or method == 'POST' and \
               not isinstance(request.response, xmlrpc.Response):
            # Probably a browser
            no_acquire_flag=0
        elif request.maybe_webdav_client:
            # Probably a WebDAV client.
            no_acquire_flag=1
        else:
            no_acquire_flag=0
        
        if hasattr(ob, '__bobo_traverse__'):
            try:
                subob = ob.__bobo_traverse__(request, name)
                if type(subob) is type(()) and len(subob) > 1:
                    # XXX Yuck! __bobo_traverse__ might return more
                    # than one object!
                    #
                    # Add additional parents into the path
                    #
                    # parents[-1:] = list(subob[:-1])
                    # ob, subob = subob[-2:]
                    raise NotImplementedError
                else:
                    return subob
            except (AttributeError, KeyError):
                raise NotFound(ob, name)

        # Should only get this far if the object doesn't have a
        # __bobo_traverse__ method.
        try:
            # Note - no_acquire_flag is necessary to support
            # things like DAV.  We have to make sure
            # that the target object is not acquired
            # if the request_method is other than GET
            # or POST. Otherwise, you could never use
            # PUT to add a new object named 'test' if
            # an object 'test' existed above it in the
            # heirarchy -- you'd always get the
            # existing object :(
            if (no_acquire_flag and hasattr(ob, 'aq_base')):
                if hasattr(ob.aq_base, name):
                    return getattr(ob, name)
                else:
                    raise AttributeError, name
            else:
                return getattr(ob, name)
        except AttributeError:
            try:
                return ob[name]
            except (KeyError, IndexError,
                    TypeError, AttributeError):
                raise NotFound(ob, name)
        
    def publishTraverse(self, request, name):
        subobject = self.subObject(request, self.context, name)

        # Ensure that the object has a docstring, or that the parent
        # object has a pseudo-docstring for the object. Objects that
        # have an empty or missing docstring are not published.
        doc = getattr(subobject, '__doc__', None)
        if doc is None:
            doc = getattr(object, '%s__doc__' % name, None)
        if not doc:
            return request.response.debugError(
                "The object at %s has an empty or missing " \
                "docstring. Objects must have a docstring to be " \
                "published." % request['URL']
                )

        # Hack for security: in Python 2.2.2, most built-in types
        # gained docstrings that they didn't have before. That caused
        # certain mutable types (dicts, lists) to become publishable
        # when they shouldn't be. The following check makes sure that
        # the right thing happens in both 2.2.2+ and earlier versions.

        if not typeCheck(subobject):
            return request.response.debugError(
                "The object at %s is not publishable." % request['URL']
                )

        return subobject

class Zope2HTTPResponse(HTTPResponse):
    
    def setResult(self, result):
        """Sets the response result value.
        """
        self.setBody(result)

    def handleException(self, exc_info):
        """Handles an otherwise unhandled exception.

        The publication object gets the first chance to handle an exception,
        and if it doesn't have a good way to do it, it defers to the
        response.  Implementations should set the reponse body.
        """
        f = StringIO()
        traceback.print_exception(
            exc_info[0]. exc_info[1], exc_info[2], 100, f)
        self.setResult(f.getvalue())

    def internalError(self):
        'See IPublisherResponse'
        self.setStatus(500, u"The engines can't take any more, Jim!")

    def getStatusString(self):
        'See IHTTPResponse'
        return '%i %s' % (self.status, status_reasons[self.status])

    def getHeaders(self):
        return self.headers.items()    
    
    def consumeBodyIter(self):
        return (self.body,)
    

class Zope2HTTPRequest(HTTPRequest):

    def supportsRetry(self):
        return False

    def traverse(self, object):
        path = self.get('PATH_INFO')
        self['PARENTS'] = [self.publication.root]

        return HTTPRequest.traverse(self, path)


def Zope2RequestFactory(sin, env):
    response=Zope2HTTPResponse() 
    return HTTPRequest(sin, env, response)

class Zope2HTTPFactory(object):

    implements(IRequestPublicationFactory)

    def canHandle(self, environment):
        return True

    def __call__(self):
        return Zope2RequestFactory, ZopePublication

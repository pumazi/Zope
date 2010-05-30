##############################################################################
#
# Copyright (c) 2009 Zope Foundation and Contributors. All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################
import unittest

class WSGIResponseTests(unittest.TestCase):

    _old_NOW = None

    def tearDown(self):
        if self._old_NOW is not None:
            self._setNOW(self._old_NOW)

    def _getTargetClass(self):
        from ZPublisher.WSGIPublisher import WSGIResponse
        return WSGIResponse

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def _setNOW(self, value):
        from ZPublisher import WSGIPublisher
        WSGIPublisher._NOW, self._old_NOW = value, WSGIPublisher._NOW

    def test_finalize_sets_204_on_empty_not_streaming(self):
        response = self._makeOne()
        response.finalize()
        self.assertEqual(response.status, 204)

    def test_finalize_sets_204_on_empty_not_streaming_ignores_non_200(self):
        response = self._makeOne()
        response.setStatus(302)
        response.finalize()
        self.assertEqual(response.status, 302)

    def test_finalize_sets_content_length_if_missing(self):
        response = self._makeOne()
        response.setBody('TESTING')
        response.finalize()
        self.assertEqual(response.getHeader('Content-Length'), '7')

    def test_finalize_skips_setting_content_length_if_missing_w_streaming(self):
        response = self._makeOne()
        response._streaming = True
        response.body = 'TESTING'
        response.finalize()
        self.failIf(response.getHeader('Content-Length'))

    def test_finalize_HTTP_1_0_keep_alive_w_content_length(self):
        response = self._makeOne()
        response._http_version = '1.0'
        response._http_connection = 'keep-alive'
        response.setBody('TESTING')
        response.finalize()
        self.assertEqual(response.getHeader('Connection'), 'Keep-Alive')

    def test_finalize_HTTP_1_0_keep_alive_wo_content_length_streaming(self):
        response = self._makeOne()
        response._http_version = '1.0'
        response._http_connection = 'keep-alive'
        response._streaming = True
        response.finalize()
        self.assertEqual(response.getHeader('Connection'), 'close')

    def test_finalize_HTTP_1_0_not_keep_alive_w_content_length(self):
        response = self._makeOne()
        response._http_version = '1.0'
        response.setBody('TESTING')
        response.finalize()
        self.assertEqual(response.getHeader('Connection'), 'close')

    def test_finalize_HTTP_1_1_connection_close(self):
        response = self._makeOne()
        response._http_version = '1.1'
        response._http_connection = 'close'
        response.finalize()
        self.assertEqual(response.getHeader('Connection'), 'close')

    def test_finalize_HTTP_1_1_wo_content_length_streaming_wo_http_chunk(self):
        response = self._makeOne()
        response._http_version = '1.1'
        response._streaming = True
        response.http_chunk = 0
        response.finalize()
        self.assertEqual(response.getHeader('Connection'), 'close')
        self.assertEqual(response.getHeader('Transfer-Encoding'), None)
        self.failIf(response._chunking)

    def test_finalize_HTTP_1_1_wo_content_length_streaming_w_http_chunk(self):
        response = self._makeOne()
        response._http_version = '1.1'
        response._streaming = True
        response.http_chunk = 1
        response.finalize()
        self.assertEqual(response.getHeader('Connection'), None)

    def test_finalize_HTTP_1_1_w_content_length_wo_chunk_wo_streaming(self):
        response = self._makeOne()
        response._http_version = '1.1'
        response.setBody('TESTING')
        response.finalize()
        self.assertEqual(response.getHeader('Connection'), None)

    def test_listHeaders_skips_Server_header_wo_server_version_set(self):
        response = self._makeOne()
        response.setBody('TESTING')
        headers = response.listHeaders()
        sv = [x for x in headers if x[0] == 'Server']
        self.failIf(sv)

    def test_listHeaders_includes_Server_header_w_server_version_set(self):
        response = self._makeOne()
        response._server_version = 'TESTME'
        response.setBody('TESTING')
        headers = response.listHeaders()
        sv = [x for x in headers if x[0] == 'Server']
        self.failUnless(('Server', 'TESTME') in sv)

    def test_listHeaders_includes_Date_header(self):
        import time
        WHEN = time.localtime()
        self._setNOW(time.mktime(WHEN))
        response = self._makeOne()
        response.setBody('TESTING')
        headers = response.listHeaders()
        whenstr = time.strftime('%a, %d %b %Y %H:%M:%S GMT',
                                time.gmtime(time.mktime(WHEN)))
        self.failUnless(('Date', whenstr) in headers)

    #def test___str__already_wrote_not_chunking(self):
    #    response = self._makeOne()
    #    response._wrote = True
    #    response._chunking = False
    #    self.assertEqual(str(response), '')

    #def test___str__already_wrote_w_chunking(self):
    #    response = self._makeOne()
    #    response._wrote = True
    #    response._chunking = True
    #    self.assertEqual(str(response), '0\r\n\r\n')

    def test___str___raises(self):
        response = self._makeOne()
        response.setBody('TESTING')
        self.assertRaises(NotImplementedError, lambda: str(response))


def noopStartResponse(status, headers):
    pass


class WSGIPublisherTests(unittest.TestCase):
    _dummy_interface = None
    
    def setUp(self):
        from zope.testing.cleanup import cleanUp

        cleanUp()
        self._registerAdapters()

    def _dummyInterface(self):
        from zope.interface import Interface
        if self._dummy_interface is not None:
            return self._dummy_interface

        class IDummy(Interface):
            """IDummy"""

        self._dummy_interface = IDummy
        return IDummy

    def _registerAdapters(self):
        from Acquisition import Implicit
        from zope.component import getGlobalSiteManager
        from zope.interface import Interface
        from zope.publisher.browser import BrowserPage
        from zope.publisher.browser import IDefaultBrowserLayer
        from zope.traversing.interfaces import ITraversable
        from zope.traversing.namespace import view
        from OFS.interfaces import IApplication

        gsm = getGlobalSiteManager()

        IDummy = self._dummyInterface()

        class TestPage(BrowserPage):
            __name__ = 'testing'
            def __call__(self):
                return 'foobar'

        # Define the views
        gsm.registerAdapter(TestPage, (IApplication, IDefaultBrowserLayer),
                            Interface, 'testing')

        # Bind the 'view' namespace (for @@ traversal)
        gsm.registerAdapter(view,
                            (IApplication, IDefaultBrowserLayer),
                            ITraversable, 'view')

    def test_publish_module_uses_setDefaultSkin(self):
        from StringIO import StringIO
                        
        self._registerAdapters()
        environ = {
            'SCRIPT_NAME' : '',
            'PATH_INFO' : '/@@testing',
            'REQUEST_METHOD' : 'GET',
            'QUERY_STRING' : '',
            'SERVER_NAME' : '127.0.0.1',
            'REMOTE_ADDR': '127.0.0.1', 
            'wsgi.url_scheme': 'http', 
            'SERVER_PORT': '80', 
            'HTTP_HOST': '127.0.0.1:80', 
            'SERVER_PROTOCOL' : 'HTTP/1.1',
            'wsgi.input' : StringIO(''),
            'CONTENT_LENGTH': '0',
            'HTTP_CONNECTION': 'keep-alive',
            'CONTENT_TYPE': ''
        }
        
        from ZPublisher.WSGIPublisher import publish_module
        self.failUnless(publish_module(environ, noopStartResponse) == ('', 'foobar'))
    

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(WSGIResponseTests, 'test'))
    suite.addTest(unittest.makeSuite(WSGIPublisherTests, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
    
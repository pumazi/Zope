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

    def test___str__already_wrote_not_chunking(self):
        response = self._makeOne()
        response._wrote = True
        response._chunking = False
        self.assertEqual(str(response), '')

    def test___str__already_wrote_w_chunking(self):
        response = self._makeOne()
        response._wrote = True
        response._chunking = True
        self.assertEqual(str(response), '0\r\n\r\n')

    def test___str__sets_204_on_empty_not_streaming(self):
        response = self._makeOne()
        str(response) # not checking value
        self.assertEqual(response.status, 204)

    def test___str__sets_204_on_empty_not_streaming_ignores_non_200(self):
        response = self._makeOne()
        response.setStatus(302)
        str(response) # not checking value
        self.assertEqual(response.status, 302)

    def test___str___sets_content_length_if_missing(self):
        response = self._makeOne()
        response.setBody('TESTING')
        str(response) # not checking value
        self.assertEqual(response.getHeader('Content-Length'),
                         str(len('TESTING')))

    def test___str___skips_setting_content_length_if_missing_w_streaming(self):
        response = self._makeOne()
        response._streaming = True
        response.body = 'TESTING'
        str(response) # not checking value
        self.failIf(response.getHeader('Content-Length'))

    def test___str___w_default_http_version(self):
        response = self._makeOne()
        response.setBody('TESTING')
        result = str(response).splitlines()
        self.assertEqual(result[0], 'HTTP/1.0 200 OK')

    def test___str___w_explicit_http_version(self):
        response = self._makeOne()
        response.setBody('TESTING')
        response._http_version = '1.1'
        result = str(response).splitlines()
        self.assertEqual(result[0], 'HTTP/1.1 200 OK')

    def test___str___skips_Server_header_wo_server_version_set(self):
        response = self._makeOne()
        response.setBody('TESTING')
        result = str(response).splitlines()
        sv = [x for x in result if x.lower().startswith('server-version')]
        self.failIf(sv)

    def test___str___includes_Server_header_w_server_version_set(self):
        response = self._makeOne()
        response._server_version = 'TESTME'
        response.setBody('TESTING')
        result = str(response).splitlines()
        self.assertEqual(result[1], 'Server: TESTME')

    def test___str___includes_Date_header(self):
        import time
        WHEN = time.localtime()
        self._setNOW(time.mktime(WHEN))
        response = self._makeOne()
        response.setBody('TESTING')
        result = str(response).splitlines()
        self.assertEqual(result[1], 'Date: %s' %
                time.strftime('%a, %d %b %Y %H:%M:%S GMT',
                              time.gmtime(time.mktime(WHEN))))

    def test___str___HTTP_1_0_keep_alive_w_content_length(self):
        response = self._makeOne()
        response._http_version = '1.0'
        response._http_connection = 'keep-alive'
        response.setBody('TESTING')
        str(response) # not checking value
        self.assertEqual(response.getHeader('Connection'), 'Keep-Alive')

    def test___str___HTTP_1_0_keep_alive_wo_content_length_streaming(self):
        response = self._makeOne()
        response._http_version = '1.0'
        response._http_connection = 'keep-alive'
        response._streaming = True
        str(response) # not checking value
        self.assertEqual(response.getHeader('Connection'), 'close')

    def test___str___HTTP_1_0_not_keep_alive_w_content_length(self):
        response = self._makeOne()
        response._http_version = '1.0'
        response.setBody('TESTING')
        str(response) # not checking value
        self.assertEqual(response.getHeader('Connection'), 'close')

    def test___str___HTTP_1_1_connection_close(self):
        response = self._makeOne()
        response._http_version = '1.1'
        response._http_connection = 'close'
        str(response) # not checking value
        self.assertEqual(response.getHeader('Connection'), 'close')

    def test___str___HTTP_1_1_wo_content_length_streaming_wo_http_chunk(self):
        response = self._makeOne()
        response._http_version = '1.1'
        response._streaming = True
        response.http_chunk = 0
        str(response) # not checking value
        self.assertEqual(response.getHeader('Connection'), 'close')
        self.assertEqual(response.getHeader('Transfer-Encoding'), None)
        self.failIf(response._chunking)

    def test___str___HTTP_1_1_wo_content_length_streaming_w_http_chunk(self):
        response = self._makeOne()
        response._http_version = '1.1'
        response._streaming = True
        response.http_chunk = 1
        str(response) # not checking value
        self.assertEqual(response.getHeader('Connection'), None)

    def test___str___HTTP_1_1_w_content_length_wo_chunk_wo_streaming(self):
        response = self._makeOne()
        response._http_version = '1.1'
        response.setBody('TESTING')
        str(response) # not checking value
        self.assertEqual(response.getHeader('Connection'), None)

    def test___str____literal_header(self):
        response = self._makeOne()
        response.headers['LiTeral-header'] = 'TESTING'
        result = str(response).splitlines()
        self.failUnless('LiTeral-header: TESTING' in result)

    def test___str____non_literal_header_no_dashes(self):
        response = self._makeOne()
        response.setHeader('literal', 'TESTING')
        result = str(response).splitlines()
        self.failUnless('Literal: TESTING' in result)

    def test___str____non_literal_header_w_dashes(self):
        response = self._makeOne()
        response.setHeader('literal-with-dashes', 'TESTING')
        result = str(response).splitlines()
        self.failUnless('Literal-With-Dashes: TESTING' in result)

    def test___str____no_cookies(self):
        response = self._makeOne()
        self.failIf('Set-Cookie' in str(response))

    def test___str____w_cookies(self):
        response = self._makeOne()
        response.setCookie('username', 'phreddy')
        result = str(response).splitlines()
        self.failUnless('Set-Cookie: username="phreddy"' in result)

    def test___str____w_accumulated_headers(self):
        response = self._makeOne()
        response.addHeader('X-username', 'phreddy')
        result = str(response).splitlines()
        self.failUnless('X-username: phreddy' in result)

    def test___str___blankline_before_body(self):
        response = self._makeOne()
        response.setBody('TESTING')
        result = str(response).splitlines()
        self.assertEqual(result[-1], 'TESTING')
        self.assertEqual(result[-2], '')


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(WSGIResponseTests))
    return suite

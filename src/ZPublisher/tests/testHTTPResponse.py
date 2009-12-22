# -*- coding: iso-8859-15 -*-

import unittest

class HTTPResponseTests(unittest.TestCase):

    def _getTargetClass(self):

        from ZPublisher.HTTPResponse import HTTPResponse
        return HTTPResponse

    def _makeOne(self, *args, **kw):

        return self._getTargetClass()(*args, **kw)

    def test_ctor_defaults(self):
        import sys
        response = self._makeOne()
        self.assertEqual(response.headers, {'status': '200 OK'}) # XXX WTF?
        self.assertEqual(response.accumulated_headers, [])
        self.assertEqual(response.status, 200)
        self.assertEqual(response.errmsg, 'OK')
        self.assertEqual(response.base, '')
        self.assertEqual(response.body, '')
        self.assertEqual(response.cookies, {})
        self.failUnless(response.stdout is sys.stdout)
        self.failUnless(response.stderr is sys.stderr)

    def test_ctor_w_body(self):
        response = self._makeOne(body='ABC')
        self.assertEqual(response.body, 'ABC')

    def test_ctor_w_headers(self):
        response = self._makeOne(headers={'foo': 'bar'})
        self.assertEqual(response.headers, {'foo': 'bar',
                                            'status': '200 OK', # XXX WTF
                                           })

    def test_ctor_w_status_code(self):
        response = self._makeOne(status=401)
        self.assertEqual(response.status, 401)
        self.assertEqual(response.errmsg, 'Unauthorized')
        self.assertEqual(response.headers,
                         {'status': '401 Unauthorized'}) # XXX WTF?

    def test_ctor_w_status_errmsg(self):
        response = self._makeOne(status='Unauthorized')
        self.assertEqual(response.status, 401)
        self.assertEqual(response.errmsg, 'Unauthorized')
        self.assertEqual(response.headers,
                         {'status': '401 Unauthorized'}) # XXX WTF?

    def test_ctor_w_status_exception(self):
        from zExceptions import Unauthorized
        response = self._makeOne(status=Unauthorized)
        self.assertEqual(response.status, 401)
        self.assertEqual(response.errmsg, 'Unauthorized')
        self.assertEqual(response.headers,
                         {'status': '401 Unauthorized'}) # XXX WTF?

    def test_ctor_charset_no_content_type_header(self):
        response = self._makeOne(body='foo')
        self.assertEqual(response.headers.get('content-type'),
                         'text/plain; charset=iso-8859-15')

    def test_ctor_charset_text_header_no_charset_defaults_latin1(self):
        response = self._makeOne(body='foo',
                                 headers={'content-type': 'text/plain'})
        self.assertEqual(response.headers.get('content-type'),
                         'text/plain; charset=iso-8859-15')

    def test_ctor_charset_application_header_no_header(self):
        response = self._makeOne(body='foo',
                                 headers={'content-type': 'application/foo'})
        self.assertEqual(response.headers.get('content-type'),
                         'application/foo')

    def test_ctor_charset_application_header_with_header(self):
        response = self._makeOne(body='foo',
                                 headers={'content-type':
                                        'application/foo; charset: something'})
        self.assertEqual(response.headers.get('content-type'),
                         'application/foo; charset: something')
    
    def test_ctor_charset_unicode_body_application_header(self):
        BODY = unicode('ärger', 'iso-8859-15')
        response = self._makeOne(body=BODY,
                                 headers={'content-type': 'application/foo'})
        self.assertEqual(response.headers.get('content-type'),
                         'application/foo; charset=iso-8859-15')
        self.assertEqual(response.body, 'ärger')

    def test_ctor_charset_unicode_body_application_header_diff_encoding(self):
        BODY = unicode('ärger', 'iso-8859-15')
        response = self._makeOne(body=BODY,
                                 headers={'content-type':
                                            'application/foo; charset=utf-8'})
        self.assertEqual(response.headers.get('content-type'),
                         'application/foo; charset=utf-8')
        # Body is re-encoded to match the header
        self.assertEqual(response.body, BODY.encode('utf-8'))

    def test_ctor_body_recodes_to_match_content_type_charset(self):
        xml = (u'<?xml version="1.0" encoding="iso-8859-15" ?>\n'
                '<foo><bar/></foo>')
        response = self._makeOne(body=xml, headers={'content-type':
                                            'text/xml; charset=utf-8'})
        self.assertEqual(response.body, xml.replace('iso-8859-15', 'utf-8'))

    def test_ctor_body_already_matches_charset_unchanged(self):
        xml = (u'<?xml version="1.0" encoding="iso-8859-15" ?>\n'
                '<foo><bar/></foo>')
        response = self._makeOne(body=xml, headers={'content-type':
                                            'text/xml; charset=iso-8859-15'})
        self.assertEqual(response.body, xml)

    def test_retry(self):
        STDOUT, STDERR = object(), object()
        response = self._makeOne(stdout=STDOUT, stderr=STDERR)
        cloned = response.retry()
        self.failUnless(isinstance(cloned, self._getTargetClass()))
        self.failUnless(cloned.stdout is STDOUT)
        self.failUnless(cloned.stderr is STDERR)

    def test_setStatus_code(self):
        response = self._makeOne()
        response.setStatus(400)
        self.assertEqual(response.status, 400)
        self.assertEqual(response.errmsg, 'Bad Request')

    def test_setStatus_errmsg(self):
        response = self._makeOne()
        response.setStatus('Bad Request')
        self.assertEqual(response.status, 400)
        self.assertEqual(response.errmsg, 'Bad Request')

    def test_setStatus_BadRequest(self):
        from zExceptions import BadRequest
        response = self._makeOne()
        response.setStatus(BadRequest)
        self.assertEqual(response.status, 400)
        self.assertEqual(response.errmsg, 'Bad Request')

    def test_setStatus_Unauthorized_exception(self):
        from zExceptions import Unauthorized
        response = self._makeOne()
        response.setStatus(Unauthorized)
        self.assertEqual(response.status, 401)
        self.assertEqual(response.errmsg, 'Unauthorized')

    def test_setStatus_Forbidden_exception(self):
        from zExceptions import Forbidden
        response = self._makeOne()
        response.setStatus(Forbidden)
        self.assertEqual(response.status, 403)
        self.assertEqual(response.errmsg, 'Forbidden')

    def test_setStatus_NotFound_exception(self):
        from zExceptions import NotFound
        response = self._makeOne()
        response.setStatus(NotFound)
        self.assertEqual(response.status, 404)
        self.assertEqual(response.errmsg, 'Not Found')

    def test_setStatus_ResourceLockedError_exception(self):
        response = self._makeOne()
        from webdav.Lockable import ResourceLockedError
        response.setStatus(ResourceLockedError)
        self.assertEqual(response.status, 423)
        self.assertEqual(response.errmsg, 'Locked')

    def test_setStatus_InternalError_exception(self):
        from zExceptions import InternalError
        response = self._makeOne()
        response.setStatus(InternalError)
        self.assertEqual(response.status, 500)
        self.assertEqual(response.errmsg, 'Internal Server Error')

    def test_setCookie_no_existing(self):
        response = self._makeOne()
        response.setCookie('foo', 'bar')
        cookie = response.cookies.get('foo', None)
        self.assertEqual(len(cookie), 1)
        self.assertEqual(cookie.get('value'), 'bar')

    def test_setCookie_w_existing(self):
        response = self._makeOne()
        response.setCookie('foo', 'bar')
        response.setCookie('foo', 'baz')
        cookie = response.cookies.get('foo', None)
        self.assertEqual(len(cookie), 1)
        self.assertEqual(cookie.get('value'), 'baz')

    def test_setCookie_no_attrs(self):
        response = self._makeOne()
        response.setCookie('foo', 'bar')
        cookies = response._cookie_list()
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0], 'Set-Cookie: foo="bar"')

    def test_setCookie_w_expires(self):
        EXPIRES = 'Wed, 31-Dec-97 23:59:59 GMT'
        response = self._makeOne()
        response.setCookie('foo', 'bar', expires=EXPIRES)
        cookie = response.cookies.get('foo', None)
        self.failUnless(cookie)
        self.assertEqual(cookie.get('value'), 'bar')
        self.assertEqual(cookie.get('expires'), EXPIRES)

        cookies = response._cookie_list()
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0],
                         'Set-Cookie: foo="bar"; Expires=%s' % EXPIRES)

    def test_setCookie_w_domain(self):
        response = self._makeOne()
        response.setCookie('foo', 'bar', domain='example.com')
        cookie = response.cookies.get('foo', None)
        self.assertEqual(len(cookie), 2)
        self.assertEqual(cookie.get('value'), 'bar')
        self.assertEqual(cookie.get('domain'), 'example.com')

        cookies = response._cookie_list()
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0],
                         'Set-Cookie: foo="bar"; Domain=example.com')

    def test_setCookie_w_path(self):
        response = self._makeOne()
        response.setCookie('foo', 'bar', path='/')
        cookie = response.cookies.get('foo', None)
        self.assertEqual(len(cookie), 2)
        self.assertEqual(cookie.get('value'), 'bar')
        self.assertEqual(cookie.get('path'), '/')

        cookies = response._cookie_list()
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0], 'Set-Cookie: foo="bar"; Path=/')

    def test_setCookie_w_comment(self):
        response = self._makeOne()
        response.setCookie('foo', 'bar', comment='COMMENT')
        cookie = response.cookies.get('foo', None)
        self.assertEqual(len(cookie), 2)
        self.assertEqual(cookie.get('value'), 'bar')
        self.assertEqual(cookie.get('comment'), 'COMMENT')

        cookies = response._cookie_list()
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0], 'Set-Cookie: foo="bar"; Comment=COMMENT')

    def test_setCookie_w_secure_true_value(self):
        response = self._makeOne()
        response.setCookie('foo', 'bar', secure='SECURE')
        cookie = response.cookies.get('foo', None)
        self.assertEqual(len(cookie), 2)
        self.assertEqual(cookie.get('value'), 'bar')
        self.assertEqual(cookie.get('secure'), 'SECURE')

        cookies = response._cookie_list()
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0], 'Set-Cookie: foo="bar"; Secure')

    def test_setCookie_w_secure_false_value(self):
        response = self._makeOne()
        response.setCookie('foo', 'bar', secure='')
        cookie = response.cookies.get('foo', None)
        self.assertEqual(len(cookie), 2)
        self.assertEqual(cookie.get('value'), 'bar')
        self.assertEqual(cookie.get('secure'), '')

        cookies = response._cookie_list()
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0], 'Set-Cookie: foo="bar"')

    def test_setCookie_w_httponly_true_value(self):
        response = self._makeOne()
        response.setCookie('foo', 'bar', http_only=True)
        cookie = response.cookies.get('foo', None)
        self.assertEqual(len(cookie), 2)
        self.assertEqual(cookie.get('value'), 'bar')
        self.assertEqual(cookie.get('http_only'), True)

        cookie_list = response._cookie_list()
        self.assertEqual(len(cookie_list), 1)
        self.assertEqual(cookie_list[0], 'Set-Cookie: foo="bar"; HTTPOnly')

    def test_setCookie_w_httponly_false_value(self):
        response = self._makeOne()
        response.setCookie('foo', 'bar', http_only=False)
        cookie = response.cookies.get('foo', None)
        self.assertEqual(len(cookie), 2)
        self.assertEqual(cookie.get('value'), 'bar')
        self.assertEqual(cookie.get('http_only'), False)

        cookie_list = response._cookie_list()
        self.assertEqual(len(cookie_list), 1)
        self.assertEqual(cookie_list[0], 'Set-Cookie: foo="bar"')

    def test_appendCookie_w_existing(self):
        response = self._makeOne()
        response.setCookie('foo', 'bar', path='/')
        response.appendCookie('foo', 'baz')
        cookie = response.cookies.get('foo', None)
        self.failUnless(cookie)
        self.assertEqual(cookie.get('value'), 'bar:baz')
        self.assertEqual(cookie.get('path'), '/')

    def test_appendCookie_no_existing(self):
        response = self._makeOne()
        response.appendCookie('foo', 'baz')
        cookie = response.cookies.get('foo', None)
        self.failUnless(cookie)
        self.assertEqual(cookie.get('value'), 'baz')

    def test_expireCookie(self):
        response = self._makeOne()
        response.expireCookie('foo', path='/')
        cookie = response.cookies.get('foo', None)
        self.failUnless(cookie)
        self.assertEqual(cookie.get('expires'), 'Wed, 31-Dec-97 23:59:59 GMT')
        self.assertEqual(cookie.get('max_age'), 0)
        self.assertEqual(cookie.get('path'), '/')

    def test_expireCookie1160(self):
        # Verify that the cookie is expired even if an expires kw arg is passed
        # http://zope.org/Collectors/Zope/1160
        response = self._makeOne()
        response.expireCookie('foo', path='/',
                              expires='Mon, 22-Mar-2004 17:59 GMT', max_age=99)
        cookie = response.cookies.get('foo', None)
        self.failUnless(cookie)
        self.assertEqual(cookie.get('expires'), 'Wed, 31-Dec-97 23:59:59 GMT')
        self.assertEqual(cookie.get('max_age'), 0)
        self.assertEqual(cookie.get('path'), '/')

    def test_getHeader_nonesuch(self):
        response = self._makeOne()
        self.assertEqual(response.getHeader('nonesuch'), None)

    def test_getHeader_existing(self):
        response = self._makeOne(headers={'foo': 'bar'})
        self.assertEqual(response.getHeader('foo'), 'bar')

    def test_getHeader_existing_not_literal(self):
        response = self._makeOne(headers={'foo': 'bar'})
        self.assertEqual(response.getHeader('Foo'), 'bar')

    def test_getHeader_existing_w_literal(self):
        response = self._makeOne(headers={'Foo': 'Bar'})
        self.assertEqual(response.getHeader('Foo', literal=True), 'Bar')

    def test_setHeader(self):
        response = self._makeOne()
        response.setHeader('foo', 'bar')
        self.assertEqual(response.getHeader('foo'), 'bar')
        self.assertEqual(response.headers.get('foo'), 'bar')
        response.setHeader('SPAM', 'eggs')
        self.assertEqual(response.getHeader('spam'), 'eggs')
        self.assertEqual(response.getHeader('SPAM'), 'eggs')

    def test_setHeader_literal(self):
        response = self._makeOne()
        response.setHeader('foo', 'bar', literal=True)
        self.assertEqual(response.getHeader('foo'), 'bar')
        response.setHeader('SPAM', 'eggs', literal=True)
        self.assertEqual(response.getHeader('SPAM', literal=True), 'eggs')
        self.assertEqual(response.getHeader('spam'), None)

    def test_setHeader_drops_CRLF(self):
        # RFC2616 disallows CRLF in a header value.
        response = self._makeOne()
        response.setHeader('Location',
                           'http://www.ietf.org/rfc/\r\nrfc2616.txt')
        self.assertEqual(response.headers['location'],
                         'http://www.ietf.org/rfc/rfc2616.txt')

    def test_setHeader_Set_Cookie_special_case(self):
        # This is crazy, given that we have APIs for cookies.  Special
        # behavior will go away in Zope 2.13
        response = self._makeOne()
        response.setHeader('Set-Cookie', 'foo="bar"')
        self.assertEqual(response.getHeader('Set-Cookie'), None)
        self.assertEqual(response.accumulated_headers,
                         [('Set-Cookie', 'foo="bar"')])

    def test_setHeader_drops_CRLF_when_accumulating(self):
        # RFC2616 disallows CRLF in a header value.
        # This is crazy, given that we have APIs for cookies.  Special
        # behavior will go away in Zope 2.13
        response = self._makeOne()
        response.setHeader('Set-Cookie', 'allowed="OK"')
        response.setHeader('Set-Cookie',
                       'violation="http://www.ietf.org/rfc/\r\nrfc2616.txt"')
        self.assertEqual(response.accumulated_headers,
                        [('Set-Cookie', 'allowed="OK"'),
                         ('Set-Cookie',
                          'violation="http://www.ietf.org/rfc/rfc2616.txt"')])

    def test_appendHeader_no_existing(self):
        response = self._makeOne()
        response.appendHeader('foo', 'foo')
        self.assertEqual(response.headers.get('foo'), 'foo')

    def test_appendHeader_no_existing_case_insensative(self):
        response = self._makeOne()
        response.appendHeader('Foo', 'foo')
        self.assertEqual(response.headers.get('foo'), 'foo')

    def test_appendHeader_w_existing(self):
        response = self._makeOne()
        response.setHeader('foo', 'bar')
        response.appendHeader('foo', 'foo')
        self.assertEqual(response.headers.get('foo'), 'bar,\r\n\tfoo')

    def test_appendHeader_w_existing_case_insenstative(self):
        response = self._makeOne()
        response.setHeader('xxx', 'bar')
        response.appendHeader('XXX', 'foo')
        self.assertEqual(response.headers.get('xxx'), 'bar,\r\n\tfoo')

    def test_appendHeader_drops_CRLF(self):
        # RFC2616 disallows CRLF in a header value.
        response = self._makeOne()
        response.appendHeader('Location',
                               'http://www.ietf.org/rfc/\r\nrfc2616.txt')
        self.assertEqual(response.headers['location'],
                         'http://www.ietf.org/rfc/rfc2616.txt')

    def test_addHeader_is_case_sensitive(self):
        response = self._makeOne()
        response.addHeader('Location', 'http://www.ietf.org/rfc/rfc2616.txt')
        self.assertEqual(response.accumulated_headers,
                         [('Location', 'http://www.ietf.org/rfc/rfc2616.txt')])

    def test_addHeader_drops_CRLF(self):
        # RFC2616 disallows CRLF in a header value.
        response = self._makeOne()
        response.addHeader('Location',
                           'http://www.ietf.org/rfc/\r\nrfc2616.txt')
        self.assertEqual(response.accumulated_headers,
                         [('Location', 'http://www.ietf.org/rfc/rfc2616.txt')])

    def test_setBase_None(self):
        response = self._makeOne()
        response.base = 'BEFORE'
        response.setBase(None)
        self.assertEqual(response.base, '')

    def test_setBase_no_trailing_path(self):
        response = self._makeOne()
        response.setBase('foo')
        self.assertEqual(response.base, 'foo/')

    def test_setBase_w_trailing_path(self):
        response = self._makeOne()
        response.setBase('foo/')
        self.assertEqual(response.base, 'foo/')

    def test_insertBase_not_HTML_no_change(self):
        response = self._makeOne()
        response.setHeader('Content-Type', 'application/pdf')
        response.setHeader('Content-Length', 8)
        response.body = 'BLAHBLAH'
        response.insertBase()
        self.assertEqual(response.body, 'BLAHBLAH')
        self.assertEqual(response.getHeader('Content-Length'), '8')

    def test_insertBase_HTML_no_base_w_head_not_munged(self):
        HTML = '<html><head></head><body></body></html>'
        response = self._makeOne()
        response.setHeader('Content-Type', 'text/html')
        response.setHeader('Content-Length', len(HTML))
        response.body = HTML
        response.insertBase()
        self.assertEqual(response.body, HTML)
        self.assertEqual(response.getHeader('Content-Length'), str(len(HTML)))

    def test_insertBase_HTML_w_base_no_head_not_munged(self):
        HTML = '<html><body></body></html>'
        response = self._makeOne()
        response.setHeader('Content-Type', 'text/html')
        response.setHeader('Content-Length', len(HTML))
        response.body = HTML
        response.insertBase()
        self.assertEqual(response.body, HTML)
        self.assertEqual(response.getHeader('Content-Length'), str(len(HTML)))

    def test_insertBase_HTML_w_base_w_head_munged(self):
        HTML = '<html><head></head><body></body></html>'
        MUNGED = ('<html><head>\n'
                  '<base href="http://example.com/base/" />\n'
                  '</head><body></body></html>')
        response = self._makeOne()
        response.setHeader('Content-Type', 'text/html')
        response.setHeader('Content-Length', 8)
        response.body = HTML
        response.setBase('http://example.com/base/')
        response.insertBase()
        self.assertEqual(response.body, MUNGED)
        self.assertEqual(response.getHeader('Content-Length'),
                         str(len(MUNGED)))

    def test_setBody_w_locking(self):
        response = self._makeOne()
        response.setBody('BEFORE', lock=True)
        result = response.setBody('AFTER')
        self.failIf(result)
        self.assertEqual(response.body, 'BEFORE')

    def test_setBody_empty_unchanged(self):
        response = self._makeOne()
        response.body = 'BEFORE'
        result = response.setBody('')
        self.failUnless(result)
        self.assertEqual(response.body, 'BEFORE')
        self.assertEqual(response.getHeader('Content-Type'), None)
        self.assertEqual(response.getHeader('Content-Length'), None)

    def test_setBody_2_tuple_wo_is_error_converted_to_HTML(self):
        EXPECTED = ("<html>\n"
                    "<head>\n<title>TITLE</title>\n</head>\n"
                    "<body>\nBODY\n</body>\n"
                    "</html>\n")
        response = self._makeOne()
        response.body = 'BEFORE'
        result = response.setBody(('TITLE', 'BODY'))
        self.failUnless(result)
        self.assertEqual(response.body, EXPECTED)
        self.assertEqual(response.getHeader('Content-Type'),
                         'text/html; charset=iso-8859-15')
        self.assertEqual(response.getHeader('Content-Length'),
                         str(len(EXPECTED)))

    def test_setBody_2_tuple_w_is_error_converted_to_Site_Error(self):
        response = self._makeOne()
        response.body = 'BEFORE'
        result = response.setBody(('TITLE', 'BODY'), is_error=True)
        self.failUnless(result)
        self.failIf('BEFORE' in response.body)
        self.failUnless('<h2>Site Error</h2>' in response.body)
        self.failUnless('TITLE' in response.body)
        self.failUnless('BODY' in response.body)
        self.assertEqual(response.getHeader('Content-Type'),
                         'text/html; charset=iso-8859-15')

    def test_setBody_string_not_HTML(self):
        response = self._makeOne()
        result = response.setBody('BODY')
        self.failUnless(result)
        self.assertEqual(response.body, 'BODY')
        self.assertEqual(response.getHeader('Content-Type'),
                         'text/plain; charset=iso-8859-15')
        self.assertEqual(response.getHeader('Content-Length'), '4')

    def test_setBody_string_HTML(self):
        HTML = '<html><head></head><body></body></html>'
        response = self._makeOne()
        result = response.setBody(HTML)
        self.failUnless(result)
        self.assertEqual(response.body, HTML)
        self.assertEqual(response.getHeader('Content-Type'),
                         'text/html; charset=iso-8859-15')
        self.assertEqual(response.getHeader('Content-Length'), str(len(HTML)))

    def test_setBody_object_with_asHTML(self):
        HTML = '<html><head></head><body></body></html>'
        class Dummy:
            def asHTML(self):
                return HTML
        response = self._makeOne()
        result = response.setBody(Dummy())
        self.failUnless(result)
        self.assertEqual(response.body, HTML)
        self.assertEqual(response.getHeader('Content-Type'),
                         'text/html; charset=iso-8859-15')
        self.assertEqual(response.getHeader('Content-Length'), str(len(HTML)))

    def test_setBody_object_with_unicode(self):
        HTML = u'<html><head></head><body><h1>Tr\u0039s Bien</h1></body></html>'
        ENCODED = HTML.encode('iso-8859-15')
        response = self._makeOne()
        result = response.setBody(HTML)
        self.failUnless(result)
        self.assertEqual(response.body, ENCODED)
        self.assertEqual(response.getHeader('Content-Type'),
                         'text/html; charset=iso-8859-15')
        self.assertEqual(response.getHeader('Content-Length'),
                         str(len(ENCODED)))

    def test_setBody_w_bogus_pseudo_HTML(self):
        # The 2001 checkin message which added the path-under-test says:
        # (r19315): "merged content type on error fixes from 2.3
        # If the str of the object returs a Python "pointer" looking mess,
        # don't let it get treated as HTML.
        from ZPublisher import NotFound
        BOGUS = '<Bogus a39d53d>'
        response = self._makeOne()
        self.assertRaises(NotFound, response.setBody, BOGUS)

    def test_setBody_html_no_charset_escapes_latin1_gt_lt(self):
        response = self._makeOne()
        BEFORE = ('<html><head></head><body><p>LT: \213</p>'
                  '<p>GT: \233</p></body></html>')
        AFTER = ('<html><head></head><body><p>LT: &lt;</p>'
                  '<p>GT: &gt;</p></body></html>')
        response.setHeader('Content-Type', 'text/html')
        result = response.setBody(BEFORE)
        self.failUnless(result)
        self.assertEqual(response.body, AFTER)
        self.assertEqual(response.getHeader('Content-Length'), str(len(AFTER)))

    def test_setBody_latin_alias_escapes_latin1_gt_lt(self):
        response = self._makeOne()
        BEFORE = ('<html><head></head><body><p>LT: \213</p>'
                  '<p>GT: \233</p></body></html>')
        AFTER = ('<html><head></head><body><p>LT: &lt;</p>'
                  '<p>GT: &gt;</p></body></html>')
        response.setHeader('Content-Type', 'text/html; charset=latin1')
        result = response.setBody(BEFORE)
        self.failUnless(result)
        self.assertEqual(response.body, AFTER)
        self.assertEqual(response.getHeader('Content-Length'), str(len(AFTER)))


    #TODO
    #def test_setBody_w_base(self):
    #def test_setBody_w_HTTP_content_compression(self):

    def test_setBody_compression_vary(self):
        # Vary header should be added here
        response = self._makeOne()
        response.enableHTTPCompression(REQUEST={'HTTP_ACCEPT_ENCODING': 'gzip'})
        response.setBody('foo'*100) # body must get smaller on compression
        self.assertEqual('Accept-Encoding' in response.getHeader('Vary'), True)
        # But here it would be unnecessary
        response = self._makeOne()
        response.enableHTTPCompression(REQUEST={'HTTP_ACCEPT_ENCODING': 'gzip'})
        response.setHeader('Vary', 'Accept-Encoding,Accept-Language')
        before = response.getHeader('Vary')
        response.setBody('foo'*100)
        self.assertEqual(before, response.getHeader('Vary'))


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(HTTPResponseTests, 'test'))
    return suite

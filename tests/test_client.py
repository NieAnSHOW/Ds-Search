"""Offline request, validation, and response-security contracts."""
import io
import json
from pathlib import Path
import ssl
import sys
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/ds-search/scripts'))
try:
    import ds_client as client
except ImportError:
    client = None

KEY = 'sk-test-only-not-a-real-credential'

class Reply(io.BytesIO):
    def __init__(self, body, status=200):
        super().__init__(body)
        self.status = status

class ClientTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(client, 'client implementation is missing')

    def request(self, kind, payload, body, **kwargs):
        class Opener:
            def open(inner, request, timeout):
                self.request_seen = request
                self.timeout_seen = timeout
                return Reply(body)
        return client.Client(KEY, opener=Opener(), **kwargs).call(kind, payload)

    def test_search_posts_official_contract_and_defaults(self):
        result = self.request('search', {'query': '中文 site:example.com', 'ori_question': None}, b'{"results": []}')
        self.assertEqual(result, {'results': []})
        self.assertEqual(self.request_seen.full_url, 'https://api.deepseek.com/v1/tools/search')
        self.assertEqual(self.request_seen.get_method(), 'POST')
        self.assertEqual(self.request_seen.get_header('Authorization'), 'Bearer ' + KEY)
        self.assertEqual(self.request_seen.get_header('Content-type'), 'application/json')
        self.assertEqual(json.loads(self.request_seen.data), {'query': '中文 site:example.com', 'count': 10, 'localization': '', 'need_content': False})
        self.assertEqual(self.timeout_seen, 30)

    def test_fetch_posts_only_validated_url(self):
        self.assertEqual(self.request('fetch', {'url':'https://example.com/a'}, b'{"title":"A","content":"# A"}'), {'title':'A','content':'# A'})
        self.assertEqual(self.request_seen.full_url, 'https://api.deepseek.com/v1/tools/fetch')
        self.assertEqual(json.loads(self.request_seen.data), {'url':'https://example.com/a'})

    def test_search_rejects_invalid_fields_types_and_boundaries(self):
        invalid = [{}, [], {'query':' '}, {'query':'x'*129}, {'query':'x','count':True}, {'query':'x','count':0}, {'query':'x','count':51}, {'query':'x','need_content':1}, {'query':'x','ori_question':''}, {'query':'x','localization':'127.0.0.999'}, {'query':'x','api_key':KEY}, {'query':'x','base_url':'https://evil.test'}]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(client.AppError):
                client.validate_input('search', data)
        for data in ({'query':'文'*128,'count':50,'localization':'::1'}, {'query':'x','localization':'1.2.3.4','ori_question':'y','need_content':True}):
            self.assertIsInstance(client.validate_input('search', data), dict)

    def test_fetch_rejects_credentials_missing_host_and_long_urls(self):
        for url in ('file:///tmp/x', 'https:///x', 'https://user:password@example.com', 'https://example.com/'+'x'*8192, 'https://example.com:bad', 'https://example.com\n/x'):
            with self.subTest(url=url), self.assertRaises(client.AppError):
                client.validate_input('fetch', {'url':url})

    def test_response_is_schema_checked_and_redacted_including_dictionary_keys(self):
        fields = {'title':KEY, 'url':'https://example.com/'+KEY, 'snippet':'hello', 'summary':'brief', 'content':'# '+KEY, 'date':'2026-10-18', 'site_name':'Example','site_icon':'https://example.com/icon','rerank_score':0.8,'authority':3,'extra':KEY}
        out = self.request('search', {'query':'x'}, json.dumps({'results':[fields]}).encode())
        self.assertNotIn(KEY, json.dumps(out))
        self.assertNotIn('extra', out['results'][0])
        self.assertEqual(set(out['results'][0]), set(fields)-{'extra'})
        self.assertNotIn(KEY, json.dumps(client.redact({KEY:[KEY]}, KEY)))
        for body in (b'{}', b'{"results":{}}', b'{"results":[1]}', b'{"results":[{"title":1,"url":"x"}]}', b'not json', b'\xff', b'{"results":[],"a":NaN}'):
            with self.subTest(body=body), self.assertRaises(client.AppError):
                self.request('search', {'query':'x'}, body)

    def test_fetch_schema_and_response_size_are_bounded(self):
        for body in (b'{"title":null,"content":"x"}', b'{"title":"x"}', b'{"title":"x","content":false}', b'x'*(8*1024*1024+1)):
            with self.subTest(size=len(body)), self.assertRaises(client.AppError):
                self.request('fetch', {'url':'https://example.com'}, body)

    def test_transient_http_errors_retry_at_most_three_times(self):
        for status in (408,429,500,503):
            events=[]
            class Opener:
                def open(inner, request, timeout):
                    events.append('request')
                    raise urllib.error.HTTPError(request.full_url,status,KEY,{},io.BytesIO(KEY.encode()))
            with self.subTest(status=status), self.assertRaises(client.AppError) as caught:
                client.Client(KEY, opener=Opener(), sleeper=lambda secs: events.append(secs)).call('search',{'query':'x'})
            self.assertEqual(events,['request',1,'request',2,'request'])
            self.assertEqual(caught.exception.status,status)
            self.assertNotIn(KEY,str(caught.exception))

    def test_permanent_http_and_transport_errors_do_not_retry_or_echo(self):
        for exc in (urllib.error.HTTPError('https://api.deepseek.com',401,KEY,{},io.BytesIO()), urllib.error.HTTPError('https://api.deepseek.com',302,KEY,{},io.BytesIO()), urllib.error.URLError(KEY), TimeoutError(KEY)):
            events=[]
            class Opener:
                def open(inner, request, timeout):
                    events.append(1)
                    raise exc
            with self.subTest(exc=type(exc)), self.assertRaises(client.AppError) as caught:
                client.Client(KEY,opener=Opener(),sleeper=lambda n:self.fail('unexpected retry')).call('search',{'query':'x'})
            self.assertEqual(events,[1])
            self.assertNotIn(KEY,str(caught.exception))

    def test_transport_ignores_environment_proxies_rejects_redirects_and_validates_tls(self):
        with patch.dict('os.environ',{'HTTPS_PROXY':'http://evil.invalid','http_proxy':'http://evil.invalid'}):
            opener=client.build_opener()
        proxies=[h for h in opener.handlers if isinstance(h,urllib.request.ProxyHandler)]
        self.assertTrue(not proxies or all(not h.proxies for h in proxies))
        https=[h for h in opener.handlers if isinstance(h,urllib.request.HTTPSHandler)][0]
        self.assertEqual(https._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(https._context.check_hostname)
        redirect=[h for h in opener.handlers if isinstance(h,urllib.request.HTTPRedirectHandler)][0]
        with self.assertRaises(client.AppError):
            redirect.redirect_request(urllib.request.Request('https://api.deepseek.com',headers={'Authorization':'Bearer '+KEY}),None,302,'',{},'https://evil.test')

    def test_official_response_types_ranges_and_required_strings(self):
        good = {'title':'A','url':'https://example.com','snippet':'s','summary':'b','content':'c','date':None,'site_name':None,'site_icon':None,'rerank_score':3,'authority':-1}
        self.assertEqual(self.request('search',{'query':'x'},json.dumps({'results':[good]}).encode())['results'][0],good)
        for field,value in (('title',None),('snippet',None),('summary',None),('content',[]),('rerank_score',True),('rerank_score',3.1),('rerank_score',-1),('authority',True),('authority',1.2),('authority',5),('authority',-2),('date',0)):
            bad = dict(good,**{field:value})
            with self.subTest(field=field,value=value),self.assertRaises(client.AppError):
                self.request('search',{'query':'x'},json.dumps({'results':[bad]}).encode())
        for field in ('title','url','snippet','summary','content'):
            bad = dict(good);del bad[field]
            with self.subTest(missing=field),self.assertRaises(client.AppError):
                self.request('search',{'query':'x'},json.dumps({'results':[bad]}).encode())

    def test_retry_can_recover_and_error_statuses_are_actionable(self):
        events=[]
        class Opener:
            def open(inner,request,timeout):
                events.append('request')
                if len(events)==1:raise urllib.error.HTTPError(request.full_url,429,'private',{},io.BytesIO())
                return Reply(b'{"results":[]}')
        self.assertEqual(client.Client(KEY,opener=Opener(),sleeper=lambda n:events.append(n)).call('search',{'query':'x'}),{'results':[]})
        self.assertEqual(events,['request',1,'request'])
        for status,code in ((401,'authentication_failed'),(402,'insufficient_balance'),(403,'permission_denied'),(404,'not_found')):
            error=client.http_error(status)
            self.assertEqual((error.code,error.status),(code,status))

    def test_request_rejects_unicode_surrogates_before_credentials_or_network(self):
        for data in ({'query':'\ud800'},{'query':'x','ori_question':'\udfff'}):
            with self.subTest(data=data),self.assertRaises(client.AppError):client.validate_input('search',data)

    def test_fetch_status_errors_explain_target_safety_and_unavailable_content(self):
        self.assertIn('安全',client.http_error(403).message)
        self.assertIn('网页',client.http_error(404).message)

    def test_short_keys_do_not_corrupt_trusted_response_field_names(self):
        for key in ('results', 'title', 'a'):
            class Opener:
                def open(inner, request, timeout):
                    return Reply(json.dumps({'results':[{'title':key,'url':'https://example.com','snippet':key,'summary':key,'content':key}]}).encode())
            result=client.Client(key,opener=Opener()).call('search',{'query':'x'})
            with self.subTest(key=key):
                self.assertEqual(set(result),{'results'})
                self.assertEqual(set(result['results'][0]),{'title','url','snippet','summary','content'})
                self.assertEqual(result['results'][0]['title'],'[REDACTED]')

import base64
import http.client
import io
import json
import threading
import unittest
import urllib.error
import urllib.parse
from unittest.mock import patch
from unittest.mock import MagicMock

import benchmark_server as bench


KEY = 'one-run+secret/ABC123'


class AdapterTests(unittest.TestCase):
    def call(self, provider, response):
        seen = []
        def transport(url, headers, payload):
            seen.append((url, headers, payload))
            return 200, response
        result = bench.search({'provider': provider, 'key': KEY, 'query': '搜索', 'top_k': 5}, transport)
        return result, seen[0]

    def test_deepseek(self):
        result, req = self.call('deepseek', {'results': [{'title': 'A', 'url': 'https://a.test', 'summary': 'S', 'date': '2026'}]})
        self.assertTrue(result['ok'])
        self.assertEqual(req[0], 'https://api.deepseek.com/v1/tools/search')
        self.assertEqual(req[2], {'query': '搜索', 'count': 5, 'need_content': True})
        self.assertEqual(result['results'][0]['published_at'], '2026')
        self.assertEqual(result['results'][0]['content_kind'], 'body')
        self.assertEqual(result['provider_mode'], 'deepseek-search')

    def test_tavily(self):
        result, req = self.call('tavily', {'results': [{'title': 'A', 'url': 'https://a.test', 'content': 'snippet', 'raw_content': 'body'}], 'usage': {'credits': 1}})
        self.assertTrue(result['ok'])
        self.assertEqual(req[1]['Authorization'], 'Bearer ' + KEY)
        self.assertFalse(req[2]['auto_parameters'])
        self.assertEqual(result['results'][0]['content'], 'body')

    def test_exa(self):
        result, req = self.call('exa', {'results': [{'title': 'A', 'url': 'https://a.test', 'text': 'body'}]})
        self.assertTrue(result['ok'])
        self.assertEqual(req[1]['x-api-key'], KEY)
        self.assertEqual(req[2]['type'], 'auto')

    def test_bocha(self):
        result, req = self.call('bocha', {'code': 200, 'data': {'webPages': {'value': [{'name': 'A', 'url': 'https://a.test', 'summary': 'body'}]}}})
        self.assertTrue(result['ok'])
        self.assertEqual(req[2]['count'], 5)
        self.assertEqual(result['results'][0]['title'], 'A')
        self.assertEqual(result['results'][0]['content_kind'], 'summary')

    def test_metaso(self):
        result, req = self.call('metaso', {'credits': 1, 'webpages': [{'title': 'A', 'link': 'https://a.test', 'snippet': 'snippet', 'summary': 'summary'}]})
        self.assertTrue(result['ok'])
        self.assertEqual(req[0], 'https://metaso.cn/api/v1/search')
        self.assertEqual(result['results'][0]['content'], 'summary')
        self.assertEqual(result['results'][0]['content_kind'], 'summary')
        self.assertEqual(result['usage'], {'credits': 1})

    def test_unknown_and_business_failures(self):
        for provider, response in [('deepseek', {}), ('deepseek', {'error': 'bad', 'results': []}), ('bocha', {'code': 401, 'data': {'webPages': {'value': []}}}), ('tavily', {'success': False, 'results': []})]:
            with self.subTest(provider=provider, response=response):
                result, _ = self.call(provider, response)
                self.assertFalse(result['ok'])
        result, _ = self.call('deepseek', {'results': []})
        self.assertTrue(result['ok'])
        self.assertEqual(result['results'], [])

    def test_invalid_result_items_do_not_become_empty(self):
        for response in [{'results': [None]}, {'results': [{'title': 'no url'}]}, {'results': 'invalid'}]:
            result, _ = self.call('deepseek', response)
            self.assertFalse(result['ok'])

    def test_secrets_removed_recursively(self):
        encodings = [KEY, urllib.parse.quote(KEY, safe=''), urllib.parse.quote_plus(KEY), base64.b64encode(KEY.encode()).decode(), KEY.encode().hex()]
        result, _ = self.call('deepseek', {'results': [{'title': ' '.join(encodings), 'url': 'https://a.test', 'content': KEY}], 'api_key': 'other-secret', 'apiToken': 'another-secret', KEY: {'authorization': 'credential', 'nested': encodings}})
        serialized = json.dumps(result)
        for value in encodings + ['other-secret', 'another-secret', 'credential']:
            self.assertNotIn(value, serialized)

    def test_encoded_bearer_and_json_auth_removed(self):
        values = ['Bearer ' + KEY, json.dumps({'api_key': KEY}), json.dumps({'Authorization': 'Bearer ' + KEY}), json.dumps({'key': KEY}, separators=(',', ':'))]
        encoded = [base64.b64encode(value.encode()).decode() for value in values]
        result, _ = self.call('deepseek', {'results': [], 'debug': encoded})
        serialized = json.dumps(result)
        for value in encoded:
            self.assertNotIn(value, serialized)

    def test_failure_preserves_safe_upstream_status(self):
        for code in [302, 401, 429]:
            def fail(*args):
                raise urllib.error.HTTPError('https://x', code, KEY, {}, None)
            result = bench.search({'provider': 'deepseek', 'key': KEY, 'query': 'x', 'top_k': 5}, fail)
            self.assertEqual(result['http_status'], code)
            self.assertNotIn(KEY, json.dumps(result))
        result, _ = self.call('deepseek', {})
        self.assertEqual(result['http_status'], 200)

    def test_unsafe_urls_rejected(self):
        for url in ['javascript:alert(1)', 'https://user:pass@a.test', 'file:///etc/passwd', 'https:///x', 'https://a.test\n.evil']:
            result, _ = self.call('deepseek', {'results': [{'url': url}]})
            self.assertFalse(result['ok'])

    def test_payload_validation(self):
        valid = {'provider': 'deepseek', 'key': KEY, 'query': 'x', 'top_k': 5}
        cases = [dict(valid, top_k=True), dict(valid, top_k=0), dict(valid, query=' '), dict(valid, query='x' * 129), dict(valid, key='x\ny'), dict(valid, provider='unknown'), dict(valid, endpoint='https://evil.test'), dict(valid, mode='advanced')]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(bench.ValidationError):
                    bench.validate_payload(payload)

    def test_transport_errors_safe(self):
        for error in [urllib.error.HTTPError('https://x', 302, KEY, {}, None), urllib.error.HTTPError('https://x', 401, KEY, {}, None), TimeoutError(KEY), ValueError(KEY)]:
            def fail(*args):
                raise error
            result = bench.search({'provider': 'deepseek', 'key': KEY, 'query': 'x', 'top_k': 5}, fail)
            self.assertFalse(result['ok'])
            self.assertNotIn(KEY, json.dumps(result))

    def test_transport_has_no_proxy_or_redirect(self):
        with patch('benchmark_server.urllib.request.build_opener') as build:
            build.return_value.open.side_effect = TimeoutError()
            with self.assertRaises(TimeoutError):
                bench.provider_transport('https://api.deepseek.com/v1/tools/search', {}, {})
            handlers = build.call_args.args
            proxy = next(x for x in handlers if isinstance(x, bench.urllib.request.ProxyHandler))
            self.assertEqual(proxy.proxies, {})
            redirect = next(x for x in handlers if isinstance(x, bench.NoRedirect))
            self.assertIsNone(redirect.redirect_request(None, None, 302, '', {}, 'https://evil.test'))

    def test_transport_response_bound_and_malformed_json(self):
        for body, headers, expected in [(b'x' * (bench.MAX_RESPONSE + 1), {}, bench.ResponseTooLarge), (b'{}', {'Content-Length': str(bench.MAX_RESPONSE + 1)}, bench.ResponseTooLarge), (b'not json', {}, ValueError), (b'{"results": [], "usage": {"credits": NaN}}', {}, ValueError)]:
            with self.subTest(expected=expected):
                response = MagicMock()
                response.__enter__.return_value = response
                response.headers = headers
                response.read.side_effect = lambda limit: body[:limit]
                with patch('benchmark_server.urllib.request.build_opener') as build:
                    build.return_value.open.return_value = response
                    with self.assertRaises(expected):
                        bench.provider_transport(bench.ENDPOINTS['deepseek'], {}, {})
                    self.assertEqual(build.return_value.open.call_args.kwargs['timeout'], 30)

    def test_results_keep_order_and_duplicates(self):
        result, _ = self.call('deepseek', {'results': [{'title': 'B', 'url': 'https://a.test'}, {'title': 'A', 'url': 'https://a.test'}]})
        self.assertEqual([(x['rank'], x['title']) for x in result['results']], [(1, 'B'), (2, 'A')])

    def test_result_limit_preserves_complete_raw(self):
        result, _ = self.call('deepseek', {'results': [{'title': str(i), 'url': 'https://a.test'} for i in range(8)]})
        self.assertEqual(len(result['results']), 5)
        self.assertEqual(len(result['raw']['results']), 8)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = bench.make_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]
        cls.host = '127.0.0.1:' + str(cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        conn.request(method, path, body, headers or {})
        res = conn.getresponse()
        result = res.status, dict(res.getheaders()), res.read()
        conn.close()
        return result

    def auth_headers(self):
        return {'Content-Type': 'application/json', 'Origin': 'http://' + self.host, 'X-Benchmark-Token': self.server.csrf_token}

    def test_health_and_allowlist(self):
        status, headers, body = self.request('GET', '/api/health')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(json.loads(body)['csrf_token'], self.server.csrf_token)
        for path in ['/README.md', '/.git/config', '/Temp.html', '/%2e%2e/README.md']:
            self.assertEqual(self.request('GET', path)[0], 404)

    def test_cross_origin_and_host_rejected(self):
        for extra in [{'Origin': 'null'}, {'Origin': 'https://evil.test'}, {'Origin': 'http://localhost:' + str(self.port)}, {'Host': 'evil.test'}, {'X-Benchmark-Token': 'wrong'}]:
            headers = self.auth_headers() | extra
            self.assertEqual(self.request('POST', '/api/search', '{}', headers)[0], 403)

    def test_missing_origin_allowed_with_token_for_cli(self):
        headers = self.auth_headers()
        del headers['Origin']
        status, _, _ = self.request('POST', '/api/search', '{}', headers)
        self.assertEqual(status, 400)

    def test_invalid_json_content_type_and_limits(self):
        for body, headers, expected in [('oops', self.auth_headers(), 400), ('{}', self.auth_headers() | {'Content-Type': 'text/plain'}, 415), ('x' * (65536 + 1), self.auth_headers(), 413)]:
            self.assertEqual(self.request('POST', '/api/search', body, headers)[0], expected)

    def test_success_real_http_mock_transport(self):
        payload = {'provider': 'deepseek', 'key': KEY, 'query': 'hello', 'top_k': 5}
        with patch('benchmark_server.provider_transport', return_value=(200, {'results': [{'title': KEY, 'url': 'https://example.com'}]})):
            status, _, body = self.request('POST', '/api/search', json.dumps(payload), self.auth_headers())
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)['ok'])
        self.assertNotIn(KEY, body.decode())

    def test_no_request_logging(self):
        with patch('sys.stderr', new_callable=io.StringIO) as stderr:
            self.request('GET', '/missing?key=' + KEY)
            self.request('POST', '/api/search', KEY, self.auth_headers())
        self.assertEqual(stderr.getvalue(), '')

    def test_duplicate_headers_and_options(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        conn.putrequest('POST', '/api/search')
        conn.putheader('Host', 'evil.test')
        conn.putheader('Content-Length', '2')
        conn.endheaders(b'{}')
        response = conn.getresponse()
        self.assertEqual(response.status, 403)
        response.read()
        conn.close()
        status, headers, _ = self.request('OPTIONS', '/api/search', headers={'Origin': 'https://evil.test'})
        self.assertEqual(status, 403)
        self.assertNotIn('Access-Control-Allow-Origin', headers)


if __name__ == '__main__':
    unittest.main()

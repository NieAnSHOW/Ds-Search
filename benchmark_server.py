#!/usr/bin/env python3
"""Loopback-only, dependency-free SearchBench API bridge. No credential storage."""

import argparse
import base64
import html
import http.server
import json
import re
import secrets
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


MAX_REQUEST = 64 * 1024
MAX_RESPONSE = 8 * 1024 * 1024
TIMEOUT = 30
ROOT = Path(__file__).resolve().parent
ENDPOINTS = {
    'deepseek': 'https://api.deepseek.com/v1/tools/search',
    'metaso': 'https://metaso.cn/api/v1/search',
    'bocha': 'https://api.bocha.cn/v1/web-search',
    'tavily': 'https://api.tavily.com/search',
    'exa': 'https://api.exa.ai/search',
}
PROVIDER_MODES = {'deepseek': 'deepseek-search', 'metaso': 'metaso-webpage-summary', 'bocha': 'bocha-web-search-summary', 'tavily': 'tavily-basic', 'exa': 'exa-auto'}
MESSAGES = {
    'invalid_request': '请求参数无效，请检查问题、引擎和密钥。',
    'forbidden': '请求来源或临时校验令牌无效，请刷新本地页面。',
    'not_found': '请求地址不存在。',
    'unsupported_media': '请使用 JSON 格式提交请求。',
    'request_too_large': '请求过大，请缩短输入。',
    'auth_failed': '上游拒绝了密钥或当前账号权限。',
    'quota_exceeded': '上游余额、额度不足或触发限流。',
    'upstream_redirect': '上游返回重定向，已停止请求。',
    'upstream_failed': '上游服务返回失败，请稍后重试。',
    'network_failed': '无法连接上游服务或请求超时。',
    'invalid_response': '上游响应格式异常，不能作为空结果计入。',
    'response_too_large': '上游响应超过大小限制。',
}


class ValidationError(ValueError):
    pass


class ResponseTooLarge(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def error(code, provider=None, elapsed_ms=None, http_status=None):
    value = {'ok': False, 'error': {'code': code, 'message': MESSAGES[code]}, 'http_status': http_status}
    if provider in ENDPOINTS:
        value['provider'] = provider
    if elapsed_ms is not None:
        value['elapsed_ms'] = elapsed_ms
    return value


def validate_payload(payload):
    if not isinstance(payload, dict) or set(payload) - {'provider', 'key', 'query', 'top_k', 'mode'}:
        raise ValidationError()
    provider, key, query = (payload.get(x) for x in ('provider', 'key', 'query'))
    if not isinstance(provider, str) or provider not in ENDPOINTS:
        raise ValidationError()
    if not isinstance(key, str) or not 1 <= len(key) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise ValidationError()
    if not isinstance(query, str) or not query.strip() or len(query) > 128 or any(ord(c) < 32 and c not in '\n\t' for c in query):
        raise ValidationError()
    top_k = payload.get('top_k', 5)
    if type(top_k) is not int or not 1 <= top_k <= 10 or payload.get('mode', 'default') != 'default':
        raise ValidationError()
    return provider, key, query, top_k


def request_config(provider, key, query, top_k):
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    headers['x-api-key' if provider == 'exa' else 'Authorization'] = key if provider == 'exa' else 'Bearer ' + key
    if provider == 'deepseek':
        params = {'query': query, 'count': top_k, 'need_content': True}
    elif provider == 'tavily':
        params = {'query': query, 'max_results': top_k, 'search_depth': 'basic', 'include_answer': False, 'include_raw_content': True, 'auto_parameters': False, 'include_usage': True, 'include_published_date': True}
    elif provider == 'exa':
        params = {'query': query, 'numResults': top_k, 'type': 'auto', 'contents': {'text': True, 'highlights': True}}
    elif provider == 'bocha':
        params = {'query': query, 'count': top_k, 'summary': True}
    else:
        params = {'q': query, 'scope': 'webpage', 'size': str(top_k), 'includeSummary': True, 'includeRawContent': False, 'conciseSnippet': False}
    return ENDPOINTS[provider], headers, params


def provider_transport(url, headers, payload):
    if url not in ENDPOINTS.values():
        raise ValueError('Endpoint is not allowed')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    request = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    with opener.open(request, timeout=TIMEOUT) as response:
        length = response.headers.get('Content-Length')
        if length and (not length.isdigit() or int(length) > MAX_RESPONSE):
            raise ResponseTooLarge()
        body = response.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE:
            raise ResponseTooLarge()
        return response.status, json.loads(body, parse_constant=reject_constant)


def reject_constant(value):
    raise ValueError('Non-finite JSON numbers are not supported')


def secret_variants(key):
    plain = {key, 'Bearer ' + key, 'bearer ' + key}
    for field_name in ('key', 'api_key', 'apiKey', 'token', 'Authorization', 'authorization'):
        for field_value in (key, 'Bearer ' + key):
            plain.add(json.dumps({field_name: field_value}))
            plain.add(json.dumps({field_name: field_value}, separators=(',', ':')))
    variants = set()
    for value in plain:
        raw = value.encode()
        variants.update((value, urllib.parse.quote(value, safe=''), urllib.parse.quote_plus(value), html.escape(value), raw.hex(), raw.hex().upper(), json.dumps(value)[1:-1], base64.b64encode(raw).decode(), base64.urlsafe_b64encode(raw).decode()))
    variants.update(x.rstrip('=') for x in list(variants) if x.endswith('='))
    variants.add(''.join('\\u%04x' % ord(c) for c in key))
    variants.add(''.join('&#%d;' % ord(c) for c in key))
    for value in list(variants):
        variants.add(urllib.parse.quote(value, safe=''))
        variants.add(re.sub(r'%[0-9A-Fa-f]{2}', lambda m: m.group().lower(), value))
    return sorted(variants, key=len, reverse=True)


SENSITIVE_FIELDS = {'authorization', 'authentication', 'apikey', 'key', 'token', 'accesstoken', 'refreshtoken', 'secret', 'password', 'credential', 'credentials', 'cookie', 'setcookie', 'xapikey'}


def sensitive_field(name):
    canonical = re.sub('[^a-z0-9]', '', str(name).lower())
    return canonical in SENSITIVE_FIELDS or canonical.endswith(('token', 'apikey', 'password', 'secret', 'credential', 'credentials'))


def scrub(value, variants):
    if isinstance(value, str):
        for secret in variants:
            value = value.replace(secret, '[REDACTED]')
        return value
    if isinstance(value, dict):
        return {scrub(str(k), variants): scrub(v, variants) for k, v in value.items() if not sensitive_field(k)}
    if isinstance(value, list):
        return [scrub(item, variants) for item in value]
    return value


def safe_url(value):
    if not isinstance(value, str) or any(ord(c) <= 32 or ord(c) == 127 for c in value) or '\\' in value:
        raise ValueError()
    parts = urllib.parse.urlsplit(value)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username is not None or parts.password is not None:
        raise ValueError()
    _ = parts.port
    return value


def field(item, *names):
    for name in names:
        value = item.get(name)
        if value is not None:
            if not isinstance(value, str):
                raise ValueError()
            return value
    return ''


def normalize(provider, raw):
    if not isinstance(raw, dict):
        raise ValueError()
    if raw.get('error') or raw.get('errors') or raw.get('detail') or raw.get('success') is False or raw.get('ok') is False:
        raise ValueError()
    if raw.get('status') in ('failed', 'failure', 'error'):
        raise ValueError()
    if 'status_code' in raw and (type(raw['status_code']) is not int or raw['status_code'] != 200):
        raise ValueError()
    if 'code' in raw and (type(raw['code']) is not int or raw['code'] not in (0, 200)):
        raise ValueError()
    if provider == 'bocha':
        if raw.get('code') != 200:
            raise ValueError()
        items = raw.get('data', {}).get('webPages', {}).get('value')
    else:
        items = raw.get('webpages' if provider == 'metaso' else 'results')
    if not isinstance(items, list):
        raise ValueError()
    results = []
    for rank, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError()
        result = {'rank': rank, 'title': field(item, 'name', 'title') if provider == 'bocha' else field(item, 'title'), 'url': safe_url(field(item, 'link', 'url') if provider == 'metaso' else field(item, 'url')), 'snippet': '', 'content': '', 'content_kind': 'summary' if provider in ('metaso', 'bocha') else 'body', 'published_at': '', 'site_name': ''}
        if provider == 'deepseek':
            result.update(snippet=field(item, 'snippet', 'summary'), content=field(item, 'content'), published_at=field(item, 'date'), site_name=field(item, 'site_name'))
        elif provider == 'tavily':
            result.update(snippet=field(item, 'content'), content=field(item, 'raw_content'), published_at=field(item, 'published_date'))
        elif provider == 'exa':
            highlights = item.get('highlights', [])
            if not isinstance(highlights, list) or not all(isinstance(v, str) for v in highlights):
                raise ValueError()
            result.update(snippet='\n'.join(highlights), content=field(item, 'text'), published_at=field(item, 'publishedDate'))
        elif provider == 'bocha':
            result.update(snippet=field(item, 'snippet'), content=field(item, 'summary'), published_at=field(item, 'datePublished'), site_name=field(item, 'siteName'))
        else:
            result.update(snippet=field(item, 'snippet'), content=field(item, 'summary'), published_at=field(item, 'date'), site_name=field(item, 'site_name'))
        results.append(result)
    return results


def search(payload, transport=None):
    provider, key, query, top_k = validate_payload(payload)
    started = time.monotonic()
    headers = params = raw = variants = None
    status = None
    try:
        url, headers, params = request_config(provider, key, query, top_k)
        status, raw = (transport or provider_transport)(url, headers, params)
        if status != 200:
            raise urllib.error.HTTPError(url, status, '', {}, None)
        results = normalize(provider, raw)[:top_k]
        usage = raw.get('usage', {})
        if not isinstance(usage, dict):
            usage = {}
        if provider == 'metaso' and isinstance(raw.get('credits'), (int, float)):
            usage = {'credits': raw['credits']}
        variants = secret_variants(key)
        return scrub({'ok': True, 'provider': provider, 'query': query, 'mode': 'default', 'provider_mode': PROVIDER_MODES[provider], 'params': params, 'elapsed_ms': round((time.monotonic() - started) * 1000), 'http_status': status, 'results': results, 'usage': usage, 'cost': None, 'raw': raw}, variants)
    except urllib.error.HTTPError as exc:
        status = exc.code
        code = 'upstream_redirect' if 300 <= exc.code < 400 else 'auth_failed' if exc.code in (401, 403) else 'quota_exceeded' if exc.code in (402, 429) else 'upstream_failed'
        if exc.fp is not None:
            exc.fp.close()
    except ResponseTooLarge:
        code = 'response_too_large'
    except (TimeoutError, OSError, urllib.error.URLError):
        code = 'network_failed'
    except (ValueError, TypeError, AttributeError, RecursionError, OverflowError):
        code = 'invalid_response'
    except Exception:
        code = 'upstream_failed'
    finally:
        key = headers = params = raw = variants = payload = None
    return error(code, provider, round((time.monotonic() - started) * 1000), http_status=status)


class BenchmarkServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        # Request paths, headers, bodies and exceptions may contain credentials.
        pass


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'SearchBench'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(TIMEOUT)

    def log_message(self, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        self.respond(code, error('invalid_request'))

    def respond(self, status, data, content_type='application/json; charset=utf-8'):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode() if isinstance(data, dict) else data
        try:
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'none'; base-uri 'none'")
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        self.close_connection = True

    def trusted(self, mutation=False):
        expected = '127.0.0.1:' + str(self.server.server_address[1])
        if self.headers.get_all('Host', []) != [expected]:
            return False
        origins = self.headers.get_all('Origin', [])
        if origins and origins != ['http://' + expected]:
            return False
        if self.headers.get('Sec-Fetch-Site') in ('cross-site', 'same-site'):
            return False
        if mutation:
            values = self.headers.get_all('X-Benchmark-Token', [])
            return len(values) == 1 and secrets.compare_digest(values[0], self.server.csrf_token)
        return True

    def do_GET(self):
        if not self.trusted():
            return self.respond(403, error('forbidden'))
        if self.path == '/api/health':
            return self.respond(200, {'ok': True, 'csrf_token': self.server.csrf_token, 'providers': list(ENDPOINTS)})
        files = {'/': ('Benchmark.html', 'text/html; charset=utf-8'), '/Benchmark.html': ('Benchmark.html', 'text/html; charset=utf-8'), '/benchmark.js': ('benchmark.js', 'text/javascript; charset=utf-8')}
        if self.path not in files:
            return self.respond(404, error('not_found'))
        name, content_type = files[self.path]
        try:
            body = (ROOT / name).read_bytes()
        except OSError:
            return self.respond(404, error('not_found'))
        self.respond(200, body, content_type)

    def do_POST(self):
        body = payload = result = None
        try:
            if not self.trusted(mutation=True):
                return self.respond(403, error('forbidden'))
            if self.path != '/api/search':
                return self.respond(404, error('not_found'))
            if self.headers.get_content_type() != 'application/json':
                return self.respond(415, error('unsupported_media'))
            lengths = self.headers.get_all('Content-Length', [])
            if self.headers.get('Transfer-Encoding') or len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                return self.respond(400, error('invalid_request'))
            length = int(lengths[0])
            if length > MAX_REQUEST:
                return self.respond(413, error('request_too_large'))
            self.connection.settimeout(TIMEOUT)
            body = self.rfile.read(length)
            if len(body) != length:
                return self.respond(400, error('invalid_request'))
            payload = json.loads(body, parse_constant=reject_constant)
            validate_payload(payload)
            result = search(payload)
            self.respond(200, result)
        except (ValueError, TypeError, UnicodeError, RecursionError, TimeoutError, OSError):
            self.respond(400, error('invalid_request'))
        finally:
            if isinstance(payload, dict):
                payload.clear()
            body = payload = result = None

    def do_OPTIONS(self):
        self.respond(403, error('forbidden'))


def make_server(port=8765):
    server = BenchmarkServer(('127.0.0.1', port), Handler)
    server.csrf_token = secrets.token_urlsafe(32)
    return server


def disable_core_dumps():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ImportError, ValueError, OSError):
        pass


def main():
    parser = argparse.ArgumentParser(description='Run the local SearchBench bridge (no credential storage).')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    disable_core_dumps()
    server = make_server(args.port)
    print('SearchBench: http://127.0.0.1:%d (Ctrl+C to stop)' % server.server_address[1])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

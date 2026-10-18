"""Bounded standard-library transport for DeepSeek's official tools API."""
import http.client
import ipaddress
import json
import math
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from ds_errors import AppError

ORIGIN = 'https://api.deepseek.com'
RESPONSE_LIMIT = 8 * 1024 * 1024
SEARCH_FIELDS = {'query', 'count', 'ori_question', 'localization', 'need_content'}
RESULT_FIELDS = {'title', 'url', 'snippet', 'summary', 'content', 'date', 'site_name', 'site_icon', 'rerank_score', 'authority'}


def invalid_input():
    return AppError('invalid_input', '输入不符合参数契约；请查看参数说明并移除不支持的字段。')


def validate_input(kind, data):
    if not isinstance(data, dict) or kind not in ('search', 'fetch'):
        raise invalid_input()
    if kind == 'fetch':
        if set(data) != {'url'}:
            raise invalid_input()
        url = data['url']
        if not isinstance(url, str) or not 1 <= len(url) <= 8192 or any(ord(c) <= 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in url):
            raise invalid_input()
        try:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username is not None or parsed.password is not None:
                raise ValueError()
            parsed.port  # Reject malformed/out-of-range ports before forwarding.
        except ValueError:
            raise invalid_input() from None
        return {'url': url}
    if any(isinstance(value, str) and any(0xD800 <= ord(char) <= 0xDFFF for char in value) for value in data.values()):
        raise invalid_input()
    if set(data) - SEARCH_FIELDS:
        raise invalid_input()
    query = data.get('query')
    if not isinstance(query, str) or not 1 <= len(query) <= 128 or not query.strip():
        raise invalid_input()
    count = data.get('count', 10)
    if type(count) is not int or not 1 <= count <= 50:
        raise invalid_input()
    need_content = data.get('need_content', False)
    if type(need_content) is not bool:
        raise invalid_input()
    localization = data.get('localization', '')
    if not isinstance(localization, str):
        raise invalid_input()
    if localization:
        try:
            ipaddress.ip_address(localization)
        except ValueError:
            raise invalid_input() from None
    result = {'query': query, 'count': count, 'localization': localization, 'need_content': need_content}
    question = data.get('ori_question')
    if question is not None:
        if not isinstance(question, str) or not 1 <= len(question) <= 128 or not question.strip():
            raise invalid_input()
        result['ori_question'] = question
    return result


def reject_constant(_value):
    raise ValueError('Invalid JSON number')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


def decode_json(raw):
    return json.loads(raw.decode('utf-8'), parse_constant=reject_constant, object_pairs_hook=unique_object)


def redact(value, key, *, scrub_keys=True):
    """Scrub strings; preserve property names only after schema validation.

    Arbitrary/untrusted dictionaries scrub their keys by default. Callers with
    a trusted protocol schema must explicitly preserve its field names.
    """
    if isinstance(value, str):
        return value.replace(key, '[REDACTED]') if key else value
    if isinstance(value, list):
        return [redact(item, key, scrub_keys=scrub_keys) for item in value]
    if isinstance(value, dict):
        return {redact(name, key) if scrub_keys else name: redact(item, key, scrub_keys=scrub_keys) for name, item in value.items()}
    return value


def invalid_response():
    return AppError('invalid_response', '服务返回了无效数据；请稍后重试或检查官方服务状态。')


def validate_response(kind, data):
    if not isinstance(data, dict):
        raise invalid_response()
    if kind == 'fetch':
        if not isinstance(data.get('title'), str) or not isinstance(data.get('content'), str):
            raise invalid_response()
        return {'title': data['title'], 'content': data['content']}
    if not isinstance(data.get('results'), list):
        raise invalid_response()
    results = []
    for item in data['results']:
        if not isinstance(item, dict) or any(not isinstance(item.get(field), str) for field in ('title', 'url', 'snippet', 'summary', 'content')):
            raise invalid_response()
        result = {}
        for field in RESULT_FIELDS & item.keys():
            value = item[field]
            if field == 'rerank_score':
                if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 3:
                    raise invalid_response()
            elif field == 'authority':
                if type(value) is not int or value not in (-1, 0, 1, 2, 3, 4):
                    raise invalid_response()
            elif value is not None and not isinstance(value, str):
                raise invalid_response()
            result[field] = value
        results.append(result)
    return {'results': results}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AppError('redirect_refused', '官方接口返回重定向，已拒绝转发认证信息。', status=code)


def build_opener():
    # Explicit empty proxy mapping prevents urllib from consulting proxy env vars.
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        NoRedirect(),
    )


def http_error(status):
    messages = {
        401: ('authentication_failed', '认证失败；请在自己的终端重新配置 API Key。'),
        402: ('insufficient_balance', '账户余额不足；请检查 DeepSeek 开放平台余额。'),
        403: ('permission_denied', '请求被安全策略拒绝；抓取时请检查目标网址是否符合平台安全规则。'),
        404: ('not_found', '未获取到可用网页内容；请检查目标网址、站点访问限制及页面格式。'),
        408: ('request_timeout', '官方请求超时；重试次数已用尽，请稍后重试。'),
        429: ('rate_limited', '已达到服务限速；请稍后重试。'),
    }
    if 300 <= status < 400:
        return AppError('redirect_refused', '官方接口返回重定向，已拒绝转发认证信息。', status)
    code, message = messages.get(status, ('service_error', '官方服务请求失败；请稍后重试或检查服务状态。'))
    return AppError(code, message, status)


class Client:
    def __init__(self, key, opener=None, sleeper=time.sleep):
        # Also validate direct library usage before constructing an HTTP header.
        from ds_credentials import validate_key
        self.key = validate_key(key)
        self.opener = opener if opener is not None else build_opener()
        self.sleeper = sleeper

    def call(self, kind, data):
        payload = validate_input(kind, data)
        request = urllib.request.Request(
            ORIGIN + '/v1/tools/' + kind,
            data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8'),
            headers={'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'},
            method='POST',
        )
        for attempt in range(3):
            try:
                with self.opener.open(request, timeout=30) as response:
                    status = response.status
                    if not 200 <= status < 300:
                        raise http_error(status)
                    raw = response.read(RESPONSE_LIMIT + 1)
                    if len(raw) > RESPONSE_LIMIT:
                        raise AppError('response_too_large', '服务响应超过 8 MiB 限制。')
                try:
                    parsed = decode_json(raw)
                except (ValueError, UnicodeError, RecursionError):
                    raise invalid_response() from None
                return redact(validate_response(kind, parsed), self.key, scrub_keys=False)
            except urllib.error.HTTPError as exc:
                status = exc.code
                exc.close()  # Never read or display the server's error body.
                if (status in (408, 429) or 500 <= status <= 599) and attempt < 2:
                    self.sleeper(attempt + 1)
                    continue
                raise http_error(status) from None
            except AppError:
                raise
            except (OSError, urllib.error.URLError, TimeoutError, http.client.HTTPException):
                raise AppError('transport_error', '网络或 TLS 连接失败；请检查网络和系统证书后重试。') from None
        raise AppError('service_error', '服务请求失败。')

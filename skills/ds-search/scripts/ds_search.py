#!/usr/bin/env python3
"""JSON CLI for the standalone ds-search Skill (Python 3.10+)."""
import argparse
import json
import platform
import sys
import warnings

import ds_credentials as credentials
from ds_client import Client, decode_json, redact, validate_input
from ds_errors import AppError

INPUT_LIMIT = 64 * 1024


class HelpRequested(Exception):
    pass


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error prints raw argv, which may contain a key.
        raise AppError('argument_error', '命令行参数无效；请使用 --help 查看支持的参数。')

    def exit(self, status=0, message=None):
        if status == 0:
            raise HelpRequested()
        raise AppError('argument_error', '请使用支持的命令与参数。')

    def print_help(self, file=None):
        super().print_help(file=sys.stderr)


def parser():
    root = SafeParser(description='DeepSeek 官方搜索/抓取；业务参数从 stdin JSON 读取。', allow_abbrev=False)
    subs = root.add_subparsers(dest='command', required=True, parser_class=SafeParser)
    for command in ('search', 'fetch'):
        sub = subs.add_parser(command, allow_abbrev=False)
        sub.add_argument('--prompt', action='store_true', help='显式选择用户交互终端的临时隐藏输入，覆盖环境变量与凭据库')
    setup = subs.add_parser('setup', allow_abbrev=False)
    setup.add_argument('--storage', choices=('keyring', 'env', 'session'), default='keyring')
    doctor = subs.add_parser('doctor', allow_abbrev=False)
    doctor.add_argument('--online', action='store_true', help='发起一次可能计费的搜索连接检查')
    subs.add_parser('forget', allow_abbrev=False)
    return root


def read_input(kind):
    raw = sys.stdin.buffer.read(INPUT_LIMIT + 1)
    if len(raw) > INPUT_LIMIT:
        raise AppError('input_too_large', 'stdin JSON 超过 64 KiB 限制。')
    try:
        data = decode_json(raw)
    except (ValueError, UnicodeError, RecursionError):
        raise AppError('invalid_input', 'stdin 必须为有效 UTF-8 JSON 对象，且字段不能重复。') from None
    # Perform validation before credentials are read or a prompt is opened.
    validate_input(kind, data)
    return data


def _main(argv=None):
    secret = None
    try:
        # Help uses stderr for UI while preserving one JSON envelope on stdout.
        args_list = list(sys.argv[1:] if argv is None else argv)
        if args_list in (['--help'], ['-h']):
            parser().print_help()
            data = {'help': True}
        else:
            args = parser().parse_args(args_list)
            if args.command == 'setup':
                print('在 https://platform.deepseek.com 创建 API Key。不要把 Key 粘贴到 Agent 聊天或命令行参数。', file=sys.stderr)
                if args.storage == 'keyring':
                    credentials.setup_keyring()
                    data = {'storage': 'keyring', 'configured': True}
                else:
                    guidance = ('由外部安全工具为当前进程注入 DEEPSEEK_API_KEY；本工具不读取 .env，也不保存普通文件。' if args.storage == 'env' else '在自己的交互终端为 search/fetch 加 --prompt；Key 只在该次进程中使用。')
                    print(guidance, file=sys.stderr)
                    data = {'storage': args.storage, 'configured': False, 'guidance': guidance}
            elif args.command == 'forget':
                credentials.forget()
                data = {'deleted': True, 'service': credentials.SERVICE, 'account': credentials.ACCOUNT}
            elif args.command == 'doctor':
                secret, source = credentials.resolve()
                data = {'credential_available': True, 'credential_source': source, 'python_version': platform.python_version(), 'platform': sys.platform, 'online': args.online}
                if args.online:
                    print('即将向官方 API 发起一次搜索；该连接检查可能计费。', file=sys.stderr)
                    result = Client(secret).call('search', {'query': 'DeepSeek', 'count': 1})
                    data['result_count'] = len(result['results'])
            else:
                payload = read_input(args.command)
                secret, source = credentials.resolve(prompt=args.prompt)
                # Client returns only schema-validated business fields. Scrub
                # their remote string values again at the CLI boundary without
                # modifying owned protocol field names, enums, or error codes.
                data = redact(Client(secret).call(args.command, payload), secret, scrub_keys=False)
        envelope = {'ok': True, 'data': data}
        status = 0
    except HelpRequested:
        envelope = {'ok': True, 'data': {'help': True}}
        status = 0
    except AppError as exc:
        envelope = {'ok': False, 'error': exc.as_dict()}
        status = 1
    except KeyboardInterrupt:
        envelope = {'ok': False, 'error': {'code': 'interrupted', 'message': '操作已取消。'}}
        status = 1
    except Exception:
        # Raw exceptions can contain credentials or untrusted response content.
        envelope = {'ok': False, 'error': {'code': 'internal_error', 'message': '操作失败；请检查输入和运行环境，不要公开凭据。'}}
        status = 1
    print(json.dumps(envelope, ensure_ascii=True, allow_nan=False))
    return status


def main(argv=None):
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        return _main(argv)


if __name__ == '__main__':
    sys.exit(main())

"""Credentials stay in process memory, environment, or a native OS store."""
import getpass
import importlib
import os
import sys
import warnings

from ds_errors import AppError

SERVICE = 'ds-search'
ACCOUNT = 'deepseek-api-key'


def validate_key(key):
    if not isinstance(key, str) or not 1 <= len(key) <= 4096 or any(not 33 <= ord(char) <= 126 for char in key):
        raise AppError('invalid_credential', 'API Key 无效；请在自己的终端重新配置，不要粘贴到聊天或命令行参数。')
    return key


def secure_backend():
    """Directly instantiate one audited native class; never discover plugins.

    keyring.get_keyring(), entry points, PYTHON_KEYRING_BACKEND and keyringrc
    are deliberately unused, so chain/plaintext/custom backends cannot win
    automatic selection. The installed keyring package itself must be trusted.
    """
    if sys.platform == 'darwin':
        module_name, class_name = 'keyring.backends.macOS', 'Keyring'
    elif sys.platform == 'win32':
        module_name, class_name = 'keyring.backends.Windows', 'WinVaultKeyring'
    elif sys.platform.startswith('linux'):
        module_name, class_name = 'keyring.backends.SecretService', 'Keyring'
    else:
        raise AppError('keyring_unavailable', '当前系统不支持安全凭据库；请使用环境变量或临时输入。')
    try:
        module = external_call(importlib.import_module, module_name)
        cls = getattr(module, class_name)
        if not isinstance(cls, type) or cls.__module__ != module_name or cls.__name__ != class_name:
            raise AppError('unsafe_keyring', '凭据库后端不受支持；拒绝明文、链式或自定义后端。')
        backend = external_call(cls)
        if type(backend) is not cls:
            raise AppError('unsafe_keyring', '凭据库后端不受支持。')
        priority = external_call(lambda: backend.priority)
        if type(priority) not in (int, float) or not priority > 0:
            raise AppError('keyring_unavailable', '安全系统凭据库不可用；请检查系统服务或使用临时输入/环境变量。')
        return backend
    except AppError:
        raise
    except Exception:
        raise AppError('keyring_unavailable', '安全系统凭据库不可用；请按初始化说明安装可选 keyring，或显式使用临时输入/环境变量。') from None


def prompt_key():
    # Business input may be piped on stdin. getpass opens the controlling
    # terminal; interactive stderr is required to prevent unattended prompts.
    if not sys.stderr.isatty():
        raise AppError('interactive_required', '隐藏输入需要用户自己的交互终端；请在终端运行或配置环境变量。')
    try:
        with warnings.catch_warnings():
            # getpass warns BEFORE its echoing fallback. Raising here prevents
            # fallback from reaching stdin.readline() on every supported Python.
            warnings.simplefilter('error')
            key = getpass.getpass('DeepSeek API Key（隐藏输入）: ', stream=sys.stderr)
    except (Warning, EOFError, OSError, KeyboardInterrupt):
        raise AppError('hidden_input_unavailable', '无法安全关闭终端回显，已中止隐藏输入。') from None
    return validate_key(key)


def external_call(function, *args):
    # Third-party warnings may contain credentials, just like exceptions.
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        return function(*args)


def resolve(prompt=False):
    if prompt:
        return prompt_key(), 'session'
    if 'DEEPSEEK_API_KEY' in os.environ:
        return validate_key(os.environ['DEEPSEEK_API_KEY']), 'environment'
    try:
        backend = secure_backend()
        key = external_call(backend.get_password, SERVICE, ACCOUNT)
    except AppError:
        raise
    except Exception:
        raise AppError('keyring_error', '无法读取系统凭据库；请解锁或修复凭据库后重试。') from None
    if key is not None:
        return validate_key(key), 'keyring'
    raise AppError('credential_missing', '未找到 API Key；请先运行 setup，或使用环境变量/显式 --prompt。')


def setup_keyring():
    backend = secure_backend()  # Reject unsafe/unavailable storage before input.
    key = prompt_key()
    try:
        external_call(backend.set_password, SERVICE, ACCOUNT, key)
    except Exception:
        raise AppError('keyring_error', '无法保存到系统凭据库；未写入普通文件，请检查凭据库状态。') from None


def forget():
    backend = secure_backend()
    try:
        external_call(backend.delete_password, SERVICE, ACCOUNT)
    except Exception:
        raise AppError('keyring_error', '无法删除本工具的凭据条目；请检查条目是否存在以及凭据库状态。') from None

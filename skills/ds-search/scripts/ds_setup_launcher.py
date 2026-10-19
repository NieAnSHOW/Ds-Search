"""Open a user-visible terminal for secure interactive credential setup."""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import warnings

import ds_credentials as credentials
from ds_errors import AppError

ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "ds_setup_terminal.py"
LAUNCH_TIMEOUT = 10

# This source is fixed: paths and commands are supplied as AppleScript argv,
# never interpolated into the script itself.
_MAC_SCRIPT = '''on run argv
    tell application "Terminal"
        activate
        do script item 1 of argv
    end tell
end run
'''


def _command() -> list[str]:
    return [os.path.abspath(sys.executable), str(RUNNER)]


def _error() -> AppError:
    return AppError('terminal_launch_failed', '无法打开安全初始化终端；请在自己的交互终端运行 setup。')


def _spawn_detached(command, **kwargs):
    # These children intentionally outlive this launcher. Dispose of our only
    # Popen reference while suppressing just its expected ResourceWarning;
    # dependency/spawn warnings still fail closed under the caller's policy.
    process = subprocess.Popen(command, **kwargs)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', ResourceWarning)
        del process


def _mac():
    command = 'exec ' + ' '.join(shlex.quote(item) for item in _command())
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            subprocess.run(
                ['/usr/bin/osascript', '-', command], input=_MAC_SCRIPT,
                text=True, capture_output=True, check=True,
                timeout=LAUNCH_TIMEOUT,
            )
    except (Exception, Warning):
        raise _error() from None


def _windows():
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0x00000010)
            # No redirects: the new console must provide native console handles
            # so stderr.isatty() and getpass retain their safety checks.
            _spawn_detached(_command(), creationflags=flags, shell=False)
    except (Exception, Warning):
        raise _error() from None


def _linux():
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        raise _error()
    command = _command()
    # Ordered from common full desktop terminals to the ubiquitous fallback.
    candidates = (
        ('gnome-terminal', ['--']),
        ('konsole', ['--separate', '-e']),
        ('xfce4-terminal', ['--disable-server', '--execute']),
        ('xterm', ['-e']),
    )
    for name, options in candidates:
        path = shutil.which(name)
        if path:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('error')
                    # The emulator creates a PTY for its child. Detach its own
                    # streams so it cannot hold open Agent tool output pipes.
                    _spawn_detached(
                        [path, *options, *command], shell=False, start_new_session=True,
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                return
            except (Exception, Warning):
                raise _error() from None
    raise _error()


def launch_setup() -> None:
    """Preflight the secure backend, then spawn a visible setup terminal."""
    credentials.secure_backend()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            if not RUNNER.is_file():
                raise _error()
            if sys.platform == 'darwin':
                _mac()
            elif sys.platform == 'win32':
                _windows()
            elif sys.platform.startswith('linux'):
                _linux()
            else:
                raise _error()
    except AppError:
        raise
    except Exception:
        raise _error() from None

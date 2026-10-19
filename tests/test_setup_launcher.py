"""Launch boundaries are mocked; no real terminal, secret, store, or network."""
import contextlib
import importlib
import io
import os
from pathlib import Path
import shlex
import subprocess
import sys
import unittest
from unittest.mock import patch
import warnings

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ds-search/scripts'
sys.path.insert(0, str(SCRIPTS))
from ds_errors import AppError


class LauncherTests(unittest.TestCase):
    def setUp(self):
        try:
            self.launcher = importlib.import_module('ds_setup_launcher')
        except ImportError:
            self.fail('dedicated setup launcher is missing')
        self.store = patch.object(self.launcher.credentials, 'secure_backend', return_value=object())
        self.store.start()
        self.addCleanup(self.store.stop)
        self.prompt = patch.object(self.launcher.credentials, 'prompt_key', side_effect=AssertionError('parent must not read a key'))
        self.prompt.start()
        self.addCleanup(self.prompt.stop)

    def test_macos_uses_fixed_applescript_and_same_absolute_interpreter(self):
        with patch.object(sys, 'platform', 'darwin'), patch.object(sys, 'executable', '/venv/bin/python3'), patch.object(self.launcher.subprocess, 'run') as run:
            self.launcher.launch_setup()
        argv = run.call_args.args[0]
        self.assertEqual(argv[:2], ['/usr/bin/osascript', '-'])
        self.assertEqual(shlex.split(argv[2]), ['exec', os.path.abspath('/venv/bin/python3'), str(SCRIPTS / 'ds_setup_terminal.py')])
        kwargs = run.call_args.kwargs
        self.assertIn('do script item 1 of argv', kwargs['input'])
        self.assertNotIn('/venv/bin/python3', kwargs['input'])
        self.assertTrue(kwargs['check'])
        self.assertTrue(kwargs['capture_output'])
        self.assertGreater(kwargs['timeout'], 0)
        self.assertLessEqual(kwargs['timeout'], 15)
        self.assertFalse(kwargs.get('shell', False))

    def test_macos_hostile_paths_round_trip_without_applescript_interpolation(self):
        hostile = '/tmp/a \' " ; $(touch nope) `id`\\folder\nend tell'
        runner_path = Path(hostile + '/ds_setup_terminal.py')
        with patch.object(sys, 'platform', 'darwin'), patch.object(sys, 'executable', hostile + '/python'), patch.object(self.launcher, 'RUNNER', runner_path), patch.object(Path, 'is_file', return_value=True), patch.object(self.launcher.subprocess, 'run') as run:
            self.launcher.launch_setup()
        argv = run.call_args.args[0]
        self.assertEqual(shlex.split(argv[2]), ['exec', os.path.abspath(hostile + '/python'), str(runner_path)])
        self.assertNotIn(hostile, run.call_args.kwargs['input'])

    def test_windows_uses_new_console_and_direct_argv(self):
        with patch.object(sys, 'platform', 'win32'), patch.object(self.launcher.subprocess, 'CREATE_NEW_CONSOLE', 16, create=True), patch.object(self.launcher.subprocess, 'Popen') as popen:
            self.launcher.launch_setup()
        self.assertEqual(popen.call_args.args[0], [os.path.abspath(sys.executable), str(SCRIPTS / 'ds_setup_terminal.py')])
        self.assertEqual(popen.call_args.kwargs['creationflags'], 16)
        self.assertFalse(popen.call_args.kwargs.get('shell', False))
        # Let CREATE_NEW_CONSOLE supply console standard handles; redirecting
        # stderr would make the existing getpass TTY guard fail closed.
        for stream in ('stdin', 'stdout', 'stderr'):
            self.assertIsNone(popen.call_args.kwargs.get(stream))

    def test_linux_uses_only_supported_terminals_with_direct_argv(self):
        terminals = {
            'gnome-terminal': ['--'],
            'konsole': ['--separate', '-e'],
            'xfce4-terminal': ['--disable-server', '--execute'],
            'xterm': ['-e'],
        }
        for name, options in terminals.items():
            with self.subTest(terminal=name), patch.object(sys, 'platform', 'linux'), patch.dict(os.environ, {'DISPLAY': ':1'}, clear=True), patch.object(self.launcher.shutil, 'which', side_effect=lambda candidate: '/usr/bin/' + candidate if candidate == name else None), patch.object(self.launcher.subprocess, 'Popen') as popen:
                self.launcher.launch_setup()
                self.assertEqual(popen.call_args.args[0], ['/usr/bin/' + name, *options, os.path.abspath(sys.executable), str(SCRIPTS / 'ds_setup_terminal.py')])
                self.assertFalse(popen.call_args.kwargs.get('shell', False))
                self.assertTrue(popen.call_args.kwargs['start_new_session'])
                for stream in ('stdin', 'stdout', 'stderr'):
                    self.assertEqual(popen.call_args.kwargs[stream], subprocess.DEVNULL)

    def test_linux_wayland_session_is_supported(self):
        with patch.object(sys, 'platform', 'linux'), patch.dict(os.environ, {'WAYLAND_DISPLAY': 'wayland-0'}, clear=True), patch.object(self.launcher.shutil, 'which', return_value='/usr/bin/gnome-terminal'), patch.object(self.launcher.subprocess, 'Popen') as popen:
            self.launcher.launch_setup()
        popen.assert_called_once()

    def test_headless_missing_terminal_and_unsupported_system_fail_without_spawn(self):
        for platform, env in (('linux', {}), ('linux', {'DISPLAY': ':1'}), ('freebsd', {})):
            with self.subTest(platform=platform, env=env), patch.object(sys, 'platform', platform), patch.dict(os.environ, env, clear=True), patch.object(self.launcher.shutil, 'which', return_value=None), patch.object(self.launcher.subprocess, 'Popen') as popen, patch.object(self.launcher.subprocess, 'run') as run:
                with self.assertRaises(AppError) as raised:
                    self.launcher.launch_setup()
                self.assertEqual(raised.exception.code, 'terminal_launch_failed')
                popen.assert_not_called()
                run.assert_not_called()

    def test_secure_backend_error_is_preserved_before_any_spawn(self):
        for code in ('keyring_unavailable', 'unsafe_keyring'):
            with self.subTest(code=code), patch.object(self.launcher.credentials, 'secure_backend', side_effect=AppError(code, 'fixed')), patch.object(self.launcher.subprocess, 'Popen') as popen, patch.object(self.launcher.subprocess, 'run') as run:
                with self.assertRaises(AppError) as raised:
                    self.launcher.launch_setup()
                self.assertEqual(raised.exception.code, code)
                popen.assert_not_called()
                run.assert_not_called()

    def test_launch_failures_timeouts_and_warnings_are_sanitized(self):
        marker = 'UNTRUSTED-EXCEPTION-DETAIL'
        failures = [OSError(marker), subprocess.TimeoutExpired(marker, 10), subprocess.CalledProcessError(1, marker, stderr=marker)]
        def warn(*args, **kwargs):
            warnings.warn(marker, RuntimeWarning)
        failures.append(warn)
        for failure in failures:
            with self.subTest(failure=failure), patch.object(sys, 'platform', 'darwin'), patch.object(self.launcher.subprocess, 'run', side_effect=failure):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr), self.assertRaises(AppError) as raised:
                    self.launcher.launch_setup()
                self.assertEqual(raised.exception.code, 'terminal_launch_failed')
                self.assertNotIn(marker, str(raised.exception) + stderr.getvalue())

    def test_discovery_failures_and_warnings_are_sanitized(self):
        marker = 'UNTRUSTED-DISCOVERY-DETAIL'
        def warn(*args, **kwargs):
            warnings.warn(marker, RuntimeWarning)
        for failure in (OSError(marker), warn):
            with self.subTest(failure=failure), patch.object(sys, 'platform', 'linux'), patch.dict(os.environ, {'DISPLAY': ':1'}, clear=True), patch.object(self.launcher.shutil, 'which', side_effect=failure):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr), self.assertRaises(AppError) as raised:
                    self.launcher.launch_setup()
                self.assertEqual(raised.exception.code, 'terminal_launch_failed')
                self.assertNotIn(marker, str(raised.exception) + stderr.getvalue())

    def test_detached_live_children_do_not_emit_unraisable_resource_warnings(self):
        # Exercise real Popen destruction under the CLI's warnings-as-errors
        # policy. Only replace the GUI command with a harmless Python child.
        program = '''
import os
import subprocess
import sys
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
import ds_search
import ds_setup_launcher as launcher
real_popen = subprocess.Popen
def harmless_child(*args, **kwargs):
    return real_popen([sys.executable, '-c', 'import time; time.sleep(0.2)'],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
with patch.object(launcher.credentials, 'secure_backend', return_value=object()), \\
     patch.object(launcher.subprocess, 'Popen', side_effect=harmless_child), \\
     patch.object(launcher.shutil, 'which', return_value='/test-terminal'), \\
     patch.object(sys, 'platform', sys.argv[2]), \\
     patch.dict(os.environ, {'DISPLAY': ':1'}):
    sys.exit(ds_search.main(['setup', '--launch']))
'''
        for platform in ('linux', 'win32'):
            with self.subTest(platform=platform):
                result = subprocess.run(
                    [sys.executable, '-c', program, str(SCRIPTS), platform],
                    capture_output=True, text=True, timeout=5,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('"launched": true', result.stdout)
                self.assertNotIn('ResourceWarning', result.stderr)
                self.assertNotIn('Exception ignored', result.stderr)
                self.assertNotIn('Traceback', result.stderr)


class TerminalRunnerTests(unittest.TestCase):
    def setUp(self):
        try:
            self.runner = importlib.import_module('ds_setup_terminal')
        except ImportError:
            self.fail('dedicated setup terminal runner is missing')

    def test_child_runs_existing_keyring_setup_then_waits_for_user(self):
        events = []
        def setup(args):
            events.append(('setup', args))
            return 0
        def wait(prompt):
            events.append(('wait', prompt))
        with patch.object(self.runner.ds_search, 'main', side_effect=setup), patch.object(sys.stdin, 'isatty', return_value=True), patch('builtins.input', side_effect=wait):
            status = self.runner.main()
        self.assertEqual(status, 0)
        self.assertEqual(events[0], ('setup', ['setup', '--storage', 'keyring']))
        self.assertEqual(events[1][0], 'wait')

    def test_child_keeps_failure_visible_and_handles_close_interrupts(self):
        for failure in (EOFError(), KeyboardInterrupt()):
            with self.subTest(failure=failure), patch.object(self.runner.ds_search, 'main', return_value=1) as setup, patch.object(sys.stdin, 'isatty', return_value=True), patch('builtins.input', side_effect=failure) as wait:
                self.assertEqual(self.runner.main(), 1)
                setup.assert_called_once_with(['setup', '--storage', 'keyring'])
                wait.assert_called_once()

    def test_headless_child_does_not_wait_on_a_pipe(self):
        with patch.object(self.runner.ds_search, 'main', return_value=1), patch.object(sys.stdin, 'isatty', return_value=False), patch('builtins.input', side_effect=AssertionError('must not wait without a terminal')):
            self.assertEqual(self.runner.main(), 1)

    def test_child_preserves_existing_noninteractive_hidden_input_guard(self):
        output, error = io.StringIO(), io.StringIO()
        with patch.object(self.runner.ds_search.credentials, 'secure_backend', return_value=object()), patch.object(self.runner.ds_search.credentials.getpass, 'getpass', side_effect=AssertionError('must not fall back to echoing input')), patch.object(sys.stdin, 'isatty', return_value=False), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            self.assertEqual(self.runner.main(), 1)
        import json
        self.assertEqual(json.loads(output.getvalue())['error']['code'], 'interactive_required')


if __name__ == '__main__':
    unittest.main()

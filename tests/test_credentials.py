"""Fake-key-only credential boundary tests; no OS stores are contacted."""
import getpass
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import warnings

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/ds-search/scripts'))
try:
    import ds_credentials as creds
except ImportError:
    creds=None

KEY='sk-test-only-not-a-real-credential'

class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(creds,'credential implementation is missing')

    def test_environment_wins_without_loading_keyring(self):
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':KEY},clear=True), patch.object(creds,'secure_backend',side_effect=AssertionError('must not read store')):
            self.assertEqual(creds.resolve(),(KEY,'environment'))

    def test_keys_reject_empty_controls_nonascii_and_excess_length(self):
        for key in ('',' ','x\ny','x\ry','x\ty','中文','x'*4097):
            with self.subTest(key=repr(key)), self.assertRaises(creds.AppError):
                creds.validate_key(key)
        self.assertEqual(creds.validate_key(KEY),KEY)

    def test_invalid_environment_fails_without_fallback(self):
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'bad\nkey'},clear=True), patch.object(creds,'secure_backend',side_effect=AssertionError('fallback')):
            with self.assertRaises(creds.AppError):creds.resolve()

    def test_keyring_read_and_forget_are_scoped(self):
        events=[]
        class Backend:
            def get_password(self,service,account):events.append(('get',service,account));return KEY
            def delete_password(self,service,account):events.append(('delete',service,account))
        with patch.dict('os.environ',{},clear=True),patch.object(creds,'secure_backend',return_value=Backend()):
            self.assertEqual(creds.resolve(),(KEY,'keyring'))
            creds.forget()
        self.assertEqual(events,[('get','ds-search','deepseek-api-key'),('delete','ds-search','deepseek-api-key')])

    def test_missing_unavailable_locked_and_invalid_store_fail_closed(self):
        for value in (None,'',KEY+'\n'):
            backend=types.SimpleNamespace(get_password=lambda *args:value)
            with patch.dict('os.environ',{},clear=True),patch.object(creds,'secure_backend',return_value=backend),self.assertRaises(creds.AppError):creds.resolve()
        backend=types.SimpleNamespace(get_password=lambda *args:(_ for _ in ()).throw(RuntimeError(KEY)))
        with patch.dict('os.environ',{},clear=True),patch.object(creds,'secure_backend',return_value=backend),self.assertRaises(creds.AppError) as caught:creds.resolve()
        self.assertNotIn(KEY,str(caught.exception))

    def test_exact_platform_backend_is_instantiated_without_discovery(self):
        for platform,module in (('darwin','keyring.backends.macOS'),('win32','keyring.backends.Windows'),('linux','keyring.backends.SecretService')):
            Native=type('WinVaultKeyring' if platform == 'win32' else 'Keyring',(),{'__module__':module,'priority':1})
            calls=[]
            def importer(name):calls.append(name);return types.SimpleNamespace(Keyring=Native,WinVaultKeyring=Native)
            with self.subTest(platform=platform),patch.object(creds.sys,'platform',platform),patch.object(creds.importlib,'import_module',side_effect=importer):
                self.assertIs(type(creds.secure_backend()),Native)
            self.assertEqual(calls,[module])

    def test_custom_plaintext_chainer_backend_classes_are_rejected(self):
        for module in ('keyrings.alt.file','keyring.backends.chainer','evil.plugin'):
            Fake=type('Keyring',(),{'__module__':module,'priority':1})
            with patch.object(creds.sys,'platform','darwin'),patch.object(creds.importlib,'import_module',return_value=types.SimpleNamespace(Keyring=Fake)),self.assertRaises(creds.AppError):creds.secure_backend()

    def test_non_tty_hidden_input_does_not_read(self):
        with patch.object(creds.sys.stdin,'isatty',return_value=False),patch.object(creds.getpass,'getpass',side_effect=AssertionError('must not prompt')),self.assertRaises(creds.AppError):creds.prompt_key()

    def test_getpass_warning_aborts_before_echo_fallback(self):
        events=[]
        def unsafe_getpass(*args,**kwargs):
            warnings.warn('cannot disable echo',getpass.GetPassWarning)
            events.append('echo fallback')
            return KEY
        with patch.object(creds.sys.stdin,'isatty',return_value=True),patch.object(creds.sys.stderr,'isatty',return_value=True),patch.object(creds.getpass,'getpass',side_effect=unsafe_getpass),self.assertRaises(creds.AppError):creds.prompt_key()
        self.assertEqual(events,[])

    def test_explicit_prompt_and_setup_use_only_selected_storage(self):
        events=[]
        backend=types.SimpleNamespace(get_password=lambda *a:None,set_password=lambda *a:events.append(a))
        with patch.dict('os.environ',{},clear=True),patch.object(creds,'secure_backend',return_value=backend),patch.object(creds,'prompt_key',return_value=KEY):
            self.assertEqual(creds.resolve(prompt=True),(KEY,'session'))
            creds.setup_keyring()
        self.assertEqual(events,[('ds-search','deepseek-api-key',KEY)])

    def test_nonviable_backend_and_dependency_warnings_fail_without_leakage(self):
        import contextlib
        import io
        for priority in (0,-1,False):
            Native=type('Keyring',(),{'__module__':'keyring.backends.macOS','priority':priority})
            with patch.object(creds.sys,'platform','darwin'),patch.object(creds.importlib,'import_module',return_value=types.SimpleNamespace(Keyring=Native)),self.assertRaises(creds.AppError):creds.secure_backend()
        err=io.StringIO()
        def warning_import(_name):
            warnings.warn(KEY,RuntimeWarning)
            raise ImportError(KEY)
        with contextlib.redirect_stderr(err),patch.object(creds.importlib,'import_module',side_effect=warning_import),self.assertRaises(creds.AppError):creds.secure_backend()
        self.assertNotIn(KEY,err.getvalue())

    def test_store_warnings_are_not_printed(self):
        import contextlib
        import io
        def warned_read(*_args):warnings.warn(KEY,RuntimeWarning);return KEY
        backend=types.SimpleNamespace(get_password=warned_read)
        err=io.StringIO()
        with patch.dict('os.environ',{},clear=True),contextlib.redirect_stderr(err),patch.object(creds,'secure_backend',return_value=backend),self.assertRaises(creds.AppError):creds.resolve()
        self.assertNotIn(KEY,err.getvalue())

    def test_prompt_explicitly_overrides_environment_and_store(self):
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':KEY},clear=True),patch.object(creds,'secure_backend',side_effect=AssertionError('must not read store')),patch.object(creds,'prompt_key',return_value='temporary-test-key'):
            self.assertEqual(creds.resolve(prompt=True),('temporary-test-key','session'))

    def test_backend_class_name_must_match_native_exact_class(self):
        Fake=type('Custom',(),{'__module__':'keyring.backends.macOS','priority':1})
        with patch.object(creds.sys,'platform','darwin'),patch.object(creds.importlib,'import_module',return_value=types.SimpleNamespace(Keyring=Fake)),self.assertRaises(creds.AppError):creds.secure_backend()

    def test_setup_and_forget_store_failures_never_expose_exception_or_warning(self):
        import contextlib
        import io
        def fail(*args):raise RuntimeError(KEY)
        backend=types.SimpleNamespace(set_password=fail,delete_password=fail)
        with patch.object(creds,'secure_backend',return_value=backend),patch.object(creds,'prompt_key',return_value=KEY):
            for action in (creds.setup_keyring,creds.forget):
                err=io.StringIO()
                with contextlib.redirect_stderr(err),self.assertRaises(creds.AppError) as caught:action()
                self.assertNotIn(KEY,str(caught.exception)+err.getvalue())

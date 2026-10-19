"""CLI executes in process or as a subprocess, with all network/store access mocked."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'skills/ds-search/scripts'
sys.path.insert(0,str(SCRIPTS))
try:
    import ds_search as cli
except ImportError:
    cli=None
KEY='sk-test-only-not-a-real-credential'

class CLITests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(cli,'CLI implementation is missing')

    def run_cli(self,args,stdin=b''):
        out,err=io.StringIO(),io.StringIO()
        input_stream=io.TextIOWrapper(io.BytesIO(stdin),encoding='utf-8')
        with patch.object(sys,'stdin',input_stream),contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            status=cli.main(args)
        self.assertNotIn(KEY,out.getvalue()+err.getvalue())
        return status,json.loads(out.getvalue()),err.getvalue()

    def test_setup_env_and_session_are_guidance_only(self):
        with patch.object(cli.credentials,'secure_backend',side_effect=AssertionError('must not read store')),patch.object(cli.credentials,'prompt_key',side_effect=AssertionError('must not read secret')):
            for storage in ('env','session'):
                code,data,err=self.run_cli(['setup','--storage',storage])
                self.assertEqual(code,0);self.assertTrue(data['ok']);self.assertTrue(err)

    def test_setup_launch_returns_only_launch_acknowledgement(self):
        with patch.object(cli.credentials,'setup_keyring',side_effect=AssertionError('must not prompt in parent')),patch.object(cli,'launch_setup',create=True) as launch:
            code,data,_=self.run_cli(['setup','--launch'])
        self.assertEqual(code,0)
        self.assertEqual(data,{'ok':True,'data':{'storage':'keyring','launched':True,'configured':False}})
        launch.assert_called_once_with()

    def test_setup_launch_rejects_guidance_modes_before_side_effects(self):
        with patch.object(cli.credentials,'secure_backend',side_effect=AssertionError('must not access store')),patch.object(cli.credentials,'prompt_key',side_effect=AssertionError('must not prompt')),patch.object(cli,'launch_setup',create=True) as launch:
            for storage in ('env','session'):
                code,data,_=self.run_cli(['setup','--storage',storage,'--launch'])
                self.assertEqual(code,1)
                self.assertEqual(data['error']['code'],'argument_error')
        launch.assert_not_called()

    def test_setup_launch_guidance_mode_rejected_in_real_noninteractive_cli(self):
        proc=subprocess.run([sys.executable,str(SCRIPTS/'ds_search.py'),'setup','--launch','--storage','env'],capture_output=True,timeout=5)
        self.assertEqual(proc.returncode,1)
        self.assertEqual(json.loads(proc.stdout)['error']['code'],'argument_error')
        self.assertNotIn(b'Traceback',proc.stderr)

    def test_argument_errors_are_json_and_do_not_echo_supplied_keys(self):
        for args in (['search','--api-key',KEY], ['oops'+KEY], ['setup','--storage',KEY], ['search','--prompt='+KEY], []):
            code,data,_=self.run_cli(args)
            self.assertNotEqual(code,0);self.assertEqual(data['error']['code'],'argument_error')

    def test_stdin_rejects_oversize_nonobject_bad_encoding_duplicate_keys_and_fields(self):
        with patch.object(cli.credentials,'resolve',side_effect=AssertionError('input must validate before credentials')):
            for body in (b'x'*65537,b'[]',b'\xff',b'{} {}',b'{"query":"x","query":"y"}',b'{"query":"x","api_key":"'+KEY.encode()+b'"}'):
                code,data,_=self.run_cli(['search'],body)
                self.assertNotEqual(code,0);self.assertFalse(data['ok'])

    def test_success_envelope_and_search_result_redaction(self):
        with patch.object(cli.credentials,'resolve',return_value=(KEY,'environment')),patch.object(cli.Client,'call',return_value={'results':[{'title':KEY,'url':'https://example.com'}]}):
            code,data,_=self.run_cli(['search'],b'{"query":"x"}')
        self.assertEqual(code,0);self.assertTrue(data['ok']);self.assertEqual(data['data']['results'][0]['title'],'[REDACTED]')

    def test_doctor_is_offline_by_default_and_online_returns_summary_only(self):
        with patch.object(cli.credentials,'resolve',return_value=(KEY,'environment')),patch.object(cli.Client,'call',return_value={'results':[{'title':'title','url':'https://example.com'}]}) as call:
            code,data,_=self.run_cli(['doctor'])
            self.assertEqual(code,0);self.assertEqual(data['data']['credential_source'],'environment');call.assert_not_called()
            code,data,err=self.run_cli(['doctor','--online'])
            self.assertEqual(code,0);self.assertEqual(data['data']['result_count'],1);self.assertNotIn('results',data['data']);self.assertTrue(err)
            call.assert_called_once_with('search',{'query':'DeepSeek','count':1})

    def test_missing_doctor_and_unknown_exceptions_are_safe_envelopes(self):
        with patch.object(cli.credentials,'resolve',side_effect=RuntimeError(KEY)):
            code,data,_=self.run_cli(['doctor'])
        self.assertNotEqual(code,0);self.assertEqual(data['error']['code'],'internal_error')

    def test_noninteractive_prompt_subprocess_fails_promptly_without_secret(self):
        env={k:v for k,v in os.environ.items() if k!='DEEPSEEK_API_KEY'}
        proc=subprocess.run([sys.executable,str(SCRIPTS/'ds_search.py'),'search','--prompt'],input=b'{"query":"x"}',capture_output=True,env=env,timeout=5)
        self.assertNotEqual(proc.returncode,0)
        self.assertFalse(json.loads(proc.stdout)['ok'])
        self.assertNotIn(b'Traceback',proc.stderr)

    def test_subcommand_help_succeeds_with_json_and_stderr_guidance(self):
        for command in ('search','fetch','doctor','forget','setup'):
            code,data,err=self.run_cli([command,'--help'])
            self.assertEqual(code,0);self.assertTrue(data['ok']);self.assertIn('usage:',err)

    def test_warnings_from_dependencies_cannot_leak_credentials(self):
        import warnings
        def warned_resolve(*args,**kwargs):warnings.warn(KEY,RuntimeWarning);return KEY,'environment'
        with patch.object(cli.credentials,'resolve',side_effect=warned_resolve):
            code,data,_=self.run_cli(['doctor'])
        self.assertNotEqual(code,0);self.assertFalse(data['ok'])

    def test_surrogates_in_api_content_emit_valid_safe_json(self):
        with patch.object(cli.credentials,'resolve',return_value=(KEY,'environment')),patch.object(cli.Client,'call',return_value={'title':'\ud800','content':'text'}):
            code,data,_=self.run_cli(['fetch'],b'{"url":"https://example.com"}')
        self.assertEqual(code,0);self.assertEqual(data['data']['title'],'\ud800')

    def test_short_keys_preserve_envelope_and_diagnostic_field_names(self):
        for key in ('a','data','credential_source','ok'):
            with patch.object(cli.credentials,'resolve',return_value=(key,'environment')):
                code,data,_=self.run_cli(['doctor'])
            with self.subTest(key=key):
                self.assertEqual(code,0)
                self.assertEqual(set(data),{'ok','data'})
                self.assertIs(data['ok'],True)
                self.assertEqual(set(data['data']),{'credential_available','credential_source','python_version','platform','online'})

    def test_short_keys_preserve_search_fields_while_scrubbing_values(self):
        with patch.object(cli.credentials,'resolve',return_value=('title','environment')),patch.object(cli.Client,'call',return_value={'results':[{'title':'title','url':'https://example.com'}]}):
            code,data,_=self.run_cli(['search'],b'{"query":"x"}')
        self.assertEqual(code,0)
        self.assertEqual(data,{'ok':True,'data':{'results':[{'title':'[REDACTED]','url':'https://example.com'}]}})

    def test_short_keys_preserve_owned_error_codes_and_diagnostic_enums(self):
        for key in ('a','authentication_failed','environment'):
            with patch.object(cli.credentials,'resolve',return_value=(key,'environment')):
                code,data,_=self.run_cli(['doctor'])
                with self.subTest(key=key,case='diagnostics'):
                    self.assertEqual(code,0)
                    self.assertEqual(data['data']['credential_source'],'environment')
            with patch.object(cli.credentials,'resolve',return_value=(key,'environment')),patch.object(cli.Client,'call',side_effect=cli.AppError('authentication_failed','认证失败',401)):
                code,data,_=self.run_cli(['doctor','--online'])
                with self.subTest(key=key,case='error'):
                    self.assertNotEqual(code,0)
                    self.assertEqual(data,{'ok':False,'error':{'code':'authentication_failed','message':'认证失败','status':401}})

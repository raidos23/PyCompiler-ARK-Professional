import os
import json
import tempfile
import unittest
from pathlib import Path

from bcasl.Loader import resolve_bcasl_timeout, run_pre_compile

class Dummy:
    def __init__(self, workspace_dir=None):
        self.workspace_dir = workspace_dir
        class L:
            def __init__(self):
                self._data = []
            def append(self, s):
                self._data.append(s)
        self.log = L()

class TestLoaderTimeoutAndRunPaths(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='bcasl_ws_'))

    def tearDown(self):
        try:
            for p in sorted(self.tmp.rglob('*'), reverse=True):
                try:
                    if p.is_file() or p.is_symlink():
                        p.unlink()
                    else:
                        p.rmdir()
                except Exception:
                    pass
            self.tmp.rmdir()
        except Exception:
            pass
        os.environ.pop('PYCOMPILER_BCASL_PLUGIN_TIMEOUT', None)

    def test_resolve_bcasl_timeout_config_over_env(self):
        ws = self.tmp
        # Config timeout should win over env
        (ws / 'bcasl.json').write_text(json.dumps({"options": {"plugin_timeout_s": 2.5}}, indent=2), encoding='utf-8')
        os.environ['PYCOMPILER_BCASL_PLUGIN_TIMEOUT'] = '10'
        d = Dummy(str(ws))
        self.assertEqual(resolve_bcasl_timeout(d), 2.5)

    def test_resolve_bcasl_timeout_env_used_when_config_zero(self):
        ws = self.tmp
        (ws / 'bcasl.json').write_text(json.dumps({"options": {"plugin_timeout_s": 0.0}}, indent=2), encoding='utf-8')
        os.environ['PYCOMPILER_BCASL_PLUGIN_TIMEOUT'] = '3.3'
        d = Dummy(str(ws))
        self.assertEqual(resolve_bcasl_timeout(d), 3.3)

    def test_run_pre_compile_skips_when_disabled(self):
        ws = self.tmp
        (ws / 'bcasl.json').write_text(json.dumps({"options": {"enabled": False}}, indent=2), encoding='utf-8')
        d = Dummy(str(ws))
        rep = run_pre_compile(d)
        self.assertIsNone(rep)

    def test_run_pre_compile_no_workspace(self):
        d = Dummy(None)
        rep = run_pre_compile(d)
        self.assertIsNone(rep)

if __name__ == '__main__':
    unittest.main()

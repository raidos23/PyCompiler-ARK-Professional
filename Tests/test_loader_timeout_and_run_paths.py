import os
import json
import unittest

from bcasl.Loader import resolve_bcasl_timeout, run_pre_compile
from .workspace_support import get_shared_workspace


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
        self.ws = get_shared_workspace()
        # Clean artifacts between runs (keep baseline ARK_Main_Config.yml)
        for name in ("bcasl.yaml", "bcasl.yml", "bcasl.json", ".bcasl.json"):
            try:
                p = self.ws / name
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        os.environ.pop("PYCOMPILER_BCASL_PLUGIN_TIMEOUT", None)

    def tearDown(self):
        # Only remove artifacts we created
        for name in ("bcasl.yaml", "bcasl.yml", "bcasl.json", ".bcasl.json"):
            try:
                p = self.ws / name
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        os.environ.pop("PYCOMPILER_BCASL_PLUGIN_TIMEOUT", None)

    def test_resolve_bcasl_timeout_config_over_env(self):
        # Config timeout should win over env
        (self.ws / "bcasl.json").write_text(
            json.dumps({"options": {"plugin_timeout_s": 2.5}}, indent=2),
            encoding="utf-8",
        )
        os.environ["PYCOMPILER_BCASL_PLUGIN_TIMEOUT"] = "10"
        d = Dummy(str(self.ws))
        self.assertEqual(resolve_bcasl_timeout(d), 2.5)

    def test_resolve_bcasl_timeout_env_used_when_config_zero(self):
        (self.ws / "bcasl.json").write_text(
            json.dumps({"options": {"plugin_timeout_s": 0.0}}, indent=2),
            encoding="utf-8",
        )
        os.environ["PYCOMPILER_BCASL_PLUGIN_TIMEOUT"] = "3.3"
        d = Dummy(str(self.ws))
        self.assertEqual(resolve_bcasl_timeout(d), 3.3)

    def test_run_pre_compile_skips_when_disabled(self):
        (self.ws / "bcasl.json").write_text(
            json.dumps({"options": {"enabled": False}}, indent=2),
            encoding="utf-8",
        )
        d = Dummy(str(self.ws))
        rep = run_pre_compile(d)
        self.assertIsNone(rep)

    def test_run_pre_compile_no_workspace(self):
        d = Dummy(None)
        rep = run_pre_compile(d)
        self.assertIsNone(rep)


if __name__ == "__main__":
    unittest.main()

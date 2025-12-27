import unittest
import json
import os
from pathlib import Path
import tempfile

from bcasl.Loader import _load_workspace_config

class TestBCASLWorkspaceConfigExtended(unittest.TestCase):
    def setUp(self):
        self.orig_cwd = Path.cwd()
        self.tmpdir = Path(tempfile.mkdtemp(prefix="bcasl_ws_"))
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        # Best-effort cleanup
        try:
            for p in sorted(self.tmpdir.rglob("*"), reverse=True):
                try:
                    if p.is_file() or p.is_symlink():
                        p.unlink()
                    elif p.is_dir():
                        p.rmdir()
                except Exception:
                    pass
            self.tmpdir.rmdir()
        except Exception:
            pass

    def write_yaml(self, name: str, content: str):
        (self.tmpdir / name).write_text(content, encoding="utf-8")

    def write_json(self, name: str, obj):
        (self.tmpdir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_default_generation_without_configs(self):
        cfg = _load_workspace_config(self.tmpdir)
        self.assertIsInstance(cfg, dict)
        # Should write a bcasl.json best-effort
        self.assertTrue((self.tmpdir / "bcasl.json").exists())
        self.assertIn("file_patterns", cfg)
        self.assertIn("exclude_patterns", cfg)
        self.assertIn("options", cfg)
        self.assertIn("plugins", cfg)
        self.assertIn("plugin_order", cfg)
        self.assertIn("enabled", cfg.get("options", {}))
        self.assertIn("plugin_timeout_s", cfg.get("options", {}))

    def test_yaml_has_priority_over_json(self):
        self.write_json("bcasl.json", {"options": {"enabled": False}})
        self.write_yaml("bcasl.yaml", "options:\n  enabled: true\n")
        cfg = _load_workspace_config(self.tmpdir)
        self.assertTrue(cfg["options"]["enabled"])  # YAML wins

    def test_json_is_used_when_no_yaml(self):
        self.write_json(".bcasl.json", {"options": {"enabled": False}})
        cfg = _load_workspace_config(self.tmpdir)
        self.assertFalse(cfg["options"]["enabled"])  # JSON honored

    def test_merge_with_ark_config_patterns(self):
        # Create ARK_Main_Config.yml to add patterns
        ark = (
            "inclusion_patterns:\n  - 'src/**/*.py'\n"
            "exclusion_patterns:\n  - '.venv/**'\n  - 'build/**'\n"
            "plugins:\n  bcasl_enabled: true\n  plugin_timeout: 1.5\n"
        )
        self.write_yaml("ARK_Main_Config.yml", ark)
        # Create minimal bcasl.yaml to be merged
        self.write_yaml("bcasl.yaml", "file_patterns:\n  - '**/*.py'\nexclude_patterns:\n  - '.git/**'\n")
        cfg = _load_workspace_config(self.tmpdir)
        # inclusion_patterns from ARK should override into file_patterns
        self.assertIn("src/**/*.py", cfg.get("file_patterns", []))
        # exclusion merged should contain both
        ex = cfg.get("exclude_patterns", [])
        self.assertIn(".venv/**", ex)
        self.assertIn("build/**", ex)
        self.assertIn(".git/**", ex)
        # plugin options merged
        self.assertTrue(cfg.get("options", {}).get("enabled", True))
        self.assertEqual(cfg.get("options", {}).get("plugin_timeout_s"), 1.5)

    def test_required_files_detection(self):
        # Ensure detection when generating default
        (self.tmpdir / "main.py").write_text("print('x')", encoding="utf-8")
        (self.tmpdir / "requirements.txt").write_text("", encoding="utf-8")
        cfg = _load_workspace_config(self.tmpdir)
        req = cfg.get("required_files", [])
        self.assertIn("main.py", req)
        self.assertIn("requirements.txt", req)

    def test_options_defaults_and_types(self):
        cfg = _load_workspace_config(self.tmpdir)
        opts = cfg.get("options", {})
        self.assertIsInstance(opts.get("enabled", True), bool)
        self.assertIsInstance(opts.get("plugin_timeout_s", 0.0), float)
        self.assertIn("sandbox", opts)
        self.assertIn("iter_files_cache", opts)

if __name__ == "__main__":
    unittest.main()

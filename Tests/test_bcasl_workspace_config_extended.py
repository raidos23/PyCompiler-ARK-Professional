import unittest
import json

from bcasl.Loader import _load_workspace_config
from .workspace_support import get_shared_workspace


class TestBCASLWorkspaceConfigExtended(unittest.TestCase):
    def setUp(self):
        self.ws = get_shared_workspace()
        # Clean artifacts possibly left by other tests (but keep baseline ARK_Main_Config.yml)
        for name in ("bcasl.yaml", "bcasl.yml", "bcasl.json", ".bcasl.json"):
            p = self.ws / name
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass

    def tearDown(self):
        # Remove only files created by this test (keep baseline ARK_Main_Config.yml)
        for name in ("bcasl.yaml", "bcasl.yml", "bcasl.json", ".bcasl.json"):
            p = self.ws / name
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass

    def write_yaml(self, name: str, content: str):
        (self.ws / name).write_text(content, encoding="utf-8")

    def write_json(self, name: str, obj):
        (self.ws / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_default_generation_without_configs(self):
        # Ensure no pre-existing bcasl configs
        for n in ("bcasl.yaml", "bcasl.yml", "bcasl.json", ".bcasl.json"):
            p = self.ws / n
            if p.exists():
                p.unlink()
        cfg = _load_workspace_config(self.ws)
        self.assertIsInstance(cfg, dict)
        # Should write a bcasl.json best-effort
        self.assertTrue((self.ws / "bcasl.json").exists())
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
        cfg = _load_workspace_config(self.ws)
        self.assertTrue(cfg["options"]["enabled"])  # YAML wins

    def test_json_is_used_when_no_yaml(self):
        self.write_json(".bcasl.json", {"options": {"enabled": False}})
        cfg = _load_workspace_config(self.ws)
        self.assertFalse(cfg["options"]["enabled"])  # JSON honored

    def test_merge_with_ark_config_patterns(self):
        # Backup existing ARK and restore after
        ark_path = self.ws / "ARK_Main_Config.yml"
        backup = None
        try:
            if ark_path.exists():
                backup = ark_path.read_text(encoding="utf-8")
        except Exception:
            backup = None

        try:
            # Write a custom ARK for this test
            ark = (
                "inclusion_patterns:\n  - 'src/**/*.py'\n"
                "exclusion_patterns:\n  - '.venv/**'\n  - 'build/**'\n"
                "plugins:\n  bcasl_enabled: true\n  plugin_timeout: 1.5\n"
            )
            self.write_yaml("ARK_Main_Config.yml", ark)
            # Create minimal bcasl.yaml to be merged
            self.write_yaml("bcasl.yaml", "file_patterns:\n  - '**/*.py'\nexclude_patterns:\n  - '.git/**'\n")
            cfg = _load_workspace_config(self.ws)
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
        finally:
            try:
                if backup is not None:
                    ark_path.write_text(backup, encoding="utf-8")
            except Exception:
                pass

    def test_required_files_detection(self):
        # Remove any pre-existing bcasl configs to force generation
        for n in ("bcasl.yaml", "bcasl.yml", "bcasl.json", ".bcasl.json"):
            p = self.ws / n
            if p.exists():
                p.unlink()
        cfg = _load_workspace_config(self.ws)
        req = cfg.get("required_files", [])
        self.assertIn("main.py", req)
        self.assertIn("requirements.txt", req)

    def test_options_defaults_and_types(self):
        cfg = _load_workspace_config(self.ws)
        opts = cfg.get("options", {})
        self.assertIsInstance(opts.get("enabled", True), bool)
        self.assertIsInstance(opts.get("plugin_timeout_s", 0.0), float)
        self.assertIn("sandbox", opts)
        self.assertIn("iter_files_cache", opts)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

class TestBCASLLoader(unittest.TestCase):
    def test_load_workspace_config_shape(self):
        from bcasl.Loader import _load_workspace_config
        cfg = _load_workspace_config(Path.cwd())
        self.assertIsInstance(cfg, dict)
        for key in ["file_patterns", "exclude_patterns", "options", "plugins", "plugin_order"]:
            self.assertIn(key, cfg)

    def test_bcasl_enabled_flag_exists(self):
        from bcasl.Loader import _load_workspace_config
        cfg = _load_workspace_config(Path.cwd())
        options = cfg.get("options", {})
        self.assertIn("enabled", options)

if __name__ == "__main__":
    unittest.main()

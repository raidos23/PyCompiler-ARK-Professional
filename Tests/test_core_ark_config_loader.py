import unittest
from pathlib import Path

class TestArkConfigLoader(unittest.TestCase):
    def test_default_config_structure(self):
        from Core.ark_config_loader import DEFAULT_CONFIG
        self.assertIsInstance(DEFAULT_CONFIG, dict)
        self.assertIn("plugins", DEFAULT_CONFIG)
        self.assertIn("bcasl_enabled", DEFAULT_CONFIG["plugins"])
        self.assertIn("plugin_timeout", DEFAULT_CONFIG["plugins"])

    def test_load_ark_config_returns_dict(self):
        from Core.ark_config_loader import load_ark_config
        cfg = load_ark_config(str(Path.cwd()))
        self.assertIsInstance(cfg, dict)
        self.assertIn("plugins", cfg)

if __name__ == "__main__":
    unittest.main()

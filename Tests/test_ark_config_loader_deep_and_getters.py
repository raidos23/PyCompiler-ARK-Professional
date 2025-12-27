import unittest
from Core.ark_config_loader import (
    _deep_merge_dict,
    DEFAULT_CONFIG,
    get_compiler_options,
    get_output_options,
    get_dependency_options,
    get_environment_manager_options,
)

class TestArkConfigLoaderDeepAndGetters(unittest.TestCase):
    def test_deep_merge_dict_nested(self):
        base = {"a": 1, "b": {"x": 1, "y": 2}, "c": {"m": {"n": 0}}}
        override = {"b": {"y": 42, "z": 9}, "c": {"m": {"n": 7}}}
        res = _deep_merge_dict(base, override)
        self.assertEqual(res["a"], 1)
        self.assertEqual(res["b"], {"x": 1, "y": 42, "z": 9})
        self.assertEqual(res["c"], {"m": {"n": 7}})

    def test_get_compiler_options_pyinstaller(self):
        opts = get_compiler_options(DEFAULT_CONFIG, "PyInstaller")
        self.assertIsInstance(opts, dict)
        self.assertIn("onefile", opts)

    def test_get_compiler_options_unknown(self):
        self.assertEqual(get_compiler_options(DEFAULT_CONFIG, "unknown"), {})

    def test_get_output_options_defaults(self):
        out = get_output_options(DEFAULT_CONFIG)
        self.assertIsInstance(out, dict)
        self.assertIn("directory", out)

    def test_get_dependency_options_defaults(self):
        deps = get_dependency_options(DEFAULT_CONFIG)
        self.assertIsInstance(deps, dict)
        self.assertIn("auto_generate_from_imports", deps)

    def test_get_environment_manager_options_defaults(self):
        env = get_environment_manager_options(DEFAULT_CONFIG)
        self.assertIsInstance(env, dict)
        self.assertIn("priority", env)

if __name__ == "__main__":
    unittest.main()

import json
import unittest
from pathlib import Path

from bcasl.Loader import _load_workspace_config
from .workspace_support import get_shared_workspace

class TestLoaderWorkspaceConfigEdgeCases(unittest.TestCase):
    def setUp(self):
        self.tmp = get_shared_workspace()
        # Clean artifacts created by previous tests if any
        for name in ('bcasl.yaml', 'bcasl.yml', 'bcasl.json', '.bcasl.json', 'ARK_Main_Config.yml'):
            try:
                p = self.tmp / name
                if p.exists():
                    p.unlink()
            except Exception:
                pass

    def tearDown(self):
        # Do not remove shared workspace; only ensure test artifacts gone
        for name in ('bcasl.yaml', 'bcasl.yml', 'bcasl.json', '.bcasl.json', 'ARK_Main_Config.yml'):
            try:
                p = self.tmp / name
                if p.exists():
                    p.unlink()
            except Exception:
                pass

    def test_yaml_empty_list_triggers_default(self):
        (self.tmp / 'bcasl.yaml').write_text('[]', encoding='utf-8')
        cfg = _load_workspace_config(self.tmp)
        self.assertIsInstance(cfg, dict)
        self.assertIn('options', cfg)
        self.assertTrue((self.tmp / 'bcasl.json').exists())

    def test_json_invalid_triggers_default(self):
        (self.tmp / '.bcasl.json').write_text('{invalid', encoding='utf-8')
        cfg = _load_workspace_config(self.tmp)
        self.assertIn('plugin_order', cfg)

    def test_exclusion_merge_dedup(self):
        (self.tmp / 'bcasl.yaml').write_text('exclude_patterns:\n  - ".venv/**"\n', encoding='utf-8')
        (self.tmp / 'ARK_Main_Config.yml').write_text('exclusion_patterns:\n  - ".venv/**"\n  - "build/**"\n', encoding='utf-8')
        cfg = _load_workspace_config(self.tmp)
        ex = cfg.get('exclude_patterns', [])
        self.assertIn('.venv/**', ex)
        self.assertIn('build/**', ex)
        self.assertLessEqual(len(ex), len(set(ex)) + 0)  # no duplicates

    def test_required_files_key_present(self):
        cfg = _load_workspace_config(self.tmp)
        self.assertIn('required_files', cfg)
        self.assertIsInstance(cfg['required_files'], list)

if __name__ == '__main__':
    unittest.main()

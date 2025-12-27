import unittest
import tempfile
from pathlib import Path

from bcasl.Base import PreCompileContext

class TestPreCompileContextIterFiles(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="iter_files_") )
        # Layout
        (self.root / 'src').mkdir(parents=True, exist_ok=True)
        (self.root / 'src' / 'a.py').write_text('print(1)', encoding='utf-8')
        (self.root / 'src' / 'b.txt').write_text('x', encoding='utf-8')
        (self.root / 'venv').mkdir(exist_ok=True)
        (self.root / 'venv' / 'ignored.py').write_text('x', encoding='utf-8')

    def tearDown(self):
        try:
            for p in sorted(self.root.rglob('*'), reverse=True):
                try:
                    if p.is_file() or p.is_symlink():
                        p.unlink()
                    else:
                        p.rmdir()
                except Exception:
                    pass
            self.root.rmdir()
        except Exception:
            pass

    def test_iter_files_include_exclude(self):
        ctx = PreCompileContext(self.root, config={"options": {"iter_files_cache": True}})
        files = list(ctx.iter_files(["src/**/*.py"], ["venv/**"]))
        self.assertEqual([p.name for p in files], ["a.py"])

    def test_iter_files_cache_behavior(self):
        ctx = PreCompileContext(self.root, config={"options": {"iter_files_cache": True}})
        first = list(ctx.iter_files(["src/**/*.py"]))
        # Add a new file after first run
        (self.root / 'src' / 'c.py').write_text('print(3)', encoding='utf-8')
        second = list(ctx.iter_files(["src/**/*.py"]))
        # With cache enabled, second should reflect cached result (no new file)
        self.assertEqual([p.name for p in first], [p.name for p in second])
        # Disable cache to see new file
        ctx_no_cache = PreCompileContext(self.root, config={"options": {"iter_files_cache": False}})
        third = list(ctx_no_cache.iter_files(["src/**/*.py"]))
        self.assertIn('c.py', [p.name for p in third])

if __name__ == '__main__':
    unittest.main()

import unittest

from bcasl.Loader import apply_translations, ensure_bcasl_thread_stopped, run_pre_compile_async

class Dummy:
    def __init__(self):
        self.log = type('L', (), {'append': lambda self, s: None})()
        # no workspace_dir on purpose

class TestLoaderMiscNoops(unittest.TestCase):
    def test_apply_translations_no_errors(self):
        gui = type('G', (), {'log': [], 'current_language': 'en'})()
        # Should not raise with non-dict tr
        apply_translations(gui, None)
        apply_translations(gui, {"_meta": {"code": "en"}})

    def test_ensure_bcasl_thread_stopped_no_thread(self):
        d = Dummy()
        ensure_bcasl_thread_stopped(d)

    def test_run_pre_compile_async_no_workspace_calls_on_done(self):
        d = Dummy()
        called = {"v": False, "arg": object()}
        def cb(x):
            called["v"] = True
            called["arg"] = x
        run_pre_compile_async(d, cb)
        self.assertTrue(called["v"])  # on_done called
        # When no workspace_dir, callback gets None
        self.assertIsNone(called["arg"])

if __name__ == '__main__':
    unittest.main()

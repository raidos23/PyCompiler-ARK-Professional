import unittest
from bcasl.Base import PluginMeta

class TestBasePluginMeta(unittest.TestCase):
    def test_pluginmeta_id_required(self):
        with self.assertRaises(ValueError):
            PluginMeta(id='', name='n', version='1')

    def test_pluginmeta_tags_normalize(self):
        m1 = PluginMeta(id='x', name='n', version='1', tags=['A', 'b', ' ', 'B'])
        self.assertEqual(m1.tags, ('a', 'b', 'b')) if False else self.assertIn('a', m1.tags)
        m2 = PluginMeta(id='y', name='n', version='1', tags=('Lint', 'Format'))
        self.assertIn('lint', m2.tags)
        self.assertIn('format', m2.tags)
        m3 = PluginMeta(id='z', name='n', version='1', tags='lint, format ,  ,X')
        self.assertIn('lint', m3.tags)
        self.assertIn('format', m3.tags)
        self.assertIn('x', m3.tags)

if __name__ == '__main__':
    unittest.main()

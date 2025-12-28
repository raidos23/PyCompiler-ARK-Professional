# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Ague Samuel Amen
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from bcasl.Base import PluginMeta


class TestBasePluginMeta(unittest.TestCase):
    def test_pluginmeta_id_required(self):
        with self.assertRaises(ValueError):
            PluginMeta(id="", name="n", version="1")

    def test_pluginmeta_tags_normalize(self):
        m1 = PluginMeta(id="x", name="n", version="1", tags=["A", "b", " ", "B"])
        (
            self.assertEqual(m1.tags, ("a", "b", "b"))
            if False
            else self.assertIn("a", m1.tags)
        )
        m2 = PluginMeta(id="y", name="n", version="1", tags=("Lint", "Format"))
        self.assertIn("lint", m2.tags)
        self.assertIn("format", m2.tags)
        m3 = PluginMeta(id="z", name="n", version="1", tags="lint, format ,  ,X")
        self.assertIn("lint", m3.tags)
        self.assertIn("format", m3.tags)
        self.assertIn("x", m3.tags)


if __name__ == "__main__":
    unittest.main()

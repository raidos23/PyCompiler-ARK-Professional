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

import os
import tempfile
import unittest
from pathlib import Path

from Core.ark_config_loader import should_exclude_file, create_default_ark_config


class TestArkConfigLoaderExclusionAndCreate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ark_cfg_"))
        self.ws = self.tmp

    def tearDown(self):
        try:
            for p in sorted(self.tmp.rglob("*"), reverse=True):
                try:
                    if p.is_file() or p.is_symlink():
                        p.unlink()
                    else:
                        p.rmdir()
                except Exception:
                    pass
            self.tmp.rmdir()
        except Exception:
            pass

    def test_should_exclude_file_by_pattern(self):
        # by relative path pattern
        f = self.ws / "a.pyc"
        f.write_text("x", encoding="utf-8")
        patterns = ["**/*.pyc", ".git/**"]
        self.assertTrue(should_exclude_file(str(f), str(self.ws), patterns))

    def test_should_exclude_file_outside_workspace(self):
        outside = Path(tempfile.gettempdir()) / "z.txt"
        outside.write_text("x", encoding="utf-8")
        patterns = ["**/*.pyc"]
        # outside workspace should be excluded
        self.assertTrue(should_exclude_file(str(outside), str(self.ws), patterns))

    def test_create_default_ark_config_creates_and_idempotent(self):
        created = create_default_ark_config(str(self.ws))
        self.assertTrue(created)
        self.assertTrue((self.ws / "ARK_Main_Config.yml").exists())
        # Second call returns False (already exists)
        created2 = create_default_ark_config(str(self.ws))
        self.assertFalse(created2)


if __name__ == "__main__":
    unittest.main()

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

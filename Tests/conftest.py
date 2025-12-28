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
import shutil
from pathlib import Path
import pytest

from .workspace_support import ensure_base_workspace, get_shared_workspace


@pytest.fixture(scope="session", autouse=True)
def prepare_base_workspace():
    """Create a base test workspace at the start of the test session.

    Sets PYCOMPILER_TEST_WORKSPACE environment variable and prepares entry point files.
    """
    ws = ensure_base_workspace()
    yield ws
    # No teardown of base workspace to allow inspection after tests if needed


@pytest.fixture()
def workspace():
    """Provide the shared test workspace under Tests/test_workspace1.

    Tests should clean up only the files they create inside this directory.
    """
    ws = get_shared_workspace()
    yield ws

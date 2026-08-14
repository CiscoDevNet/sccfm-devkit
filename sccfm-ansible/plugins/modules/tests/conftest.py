# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Test configuration for Ansible module tests.

This conftest sets up the module import structure so that pytest can import
Ansible modules despite them being in an Ansible collection (not a standard
Python package). It creates a fake package hierarchy in sys.modules:

    plugins/
        modules/
            <module_name>  <- the modules we're testing
        module_utils/
            config         <- shared dependencies

Without this setup, imports like `from plugins.modules import <module_name>` would fail
because Ansible collections use relative imports (..module_utils) that require
the parent package structure to exist.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest
from _pytest.monkeypatch import MonkeyPatch

from cisco_sccfm_core.models.profile import Profile

# Set environment variable that Ansible uses for module argument passing
os.environ.setdefault("ANSIBLE_MODULE_ARGS", "{}")

# Load config module directly
module_utils_path = Path(__file__).parent.parent.parent / "module_utils"
config_path = module_utils_path / "config.py"
spec = importlib.util.spec_from_file_location("config", config_path)
assert spec is not None and spec.loader is not None
config_module = importlib.util.module_from_spec(spec)
sys.modules["config"] = config_module  # Add to sys.modules before executing
spec.loader.exec_module(config_module)

# Create proper package hierarchy
plugins_module = ModuleType("plugins")
plugins_module.__path__ = [str(Path(__file__).parent.parent.parent)]
plugins_module.__package__ = "plugins"
sys.modules["plugins"] = plugins_module

modules_module = ModuleType("plugins.modules")
modules_module.__path__ = [str(Path(__file__).parent.parent)]
modules_module.__package__ = "plugins.modules"
sys.modules["plugins.modules"] = modules_module

module_utils_module = ModuleType("plugins.module_utils")
module_utils_module.__path__ = [str(module_utils_path)]
module_utils_module.__package__ = "plugins.module_utils"
sys.modules["plugins.module_utils"] = module_utils_module

# Add config as a submodule with all exports
config_submodule = ModuleType("plugins.module_utils.config")
config_submodule.Config = config_module.Config
config_submodule.base_argument_spec = config_module.base_argument_spec
config_submodule.identifier_argument_spec = config_module.identifier_argument_spec
config_submodule.create_config = config_module.create_config
config_submodule.__package__ = "plugins.module_utils"
sys.modules["plugins.module_utils.config"] = config_submodule

# Load operations module directly
operations_path = module_utils_path / "operations.py"
ops_spec = importlib.util.spec_from_file_location("operations", operations_path)
assert ops_spec is not None and ops_spec.loader is not None
operations_module = importlib.util.module_from_spec(ops_spec)
sys.modules["operations"] = operations_module
ops_spec.loader.exec_module(operations_module)

# Add operations as a submodule
operations_submodule = ModuleType("plugins.module_utils.operations")
operations_submodule.fetch_object_by_identifier = operations_module.fetch_object_by_identifier
operations_submodule.run_delete_with_idempotency = operations_module.run_delete_with_idempotency
operations_submodule.fields_need_update = operations_module.fields_need_update
operations_submodule.__package__ = "plugins.module_utils"
sys.modules["plugins.module_utils.operations"] = operations_submodule


@pytest.fixture(autouse=True)
def configured_sccfm_profile(monkeypatch: MonkeyPatch) -> None:
    """Keep module tests isolated from the user's canonical profile file."""
    monkeypatch.setattr(
        config_module.ProfileService,
        "load",
        lambda _service, profile: Profile(
            profile=profile,
            region="us",
            api_token="test-token-123",
        ),
    )

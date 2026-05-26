# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from importlib import import_module
from typing import Any


def assert_module_contract(module_name: str) -> None:
    module: Any = import_module(f"plugins.modules.{module_name}")

    assert f"module: {module_name}" in module.DOCUMENTATION
    assert module.EXAMPLES.strip()
    assert module.RETURN.strip()

    argument_spec = module.build_argument_spec()
    assert "region" in argument_spec
    assert "api_token" in argument_spec

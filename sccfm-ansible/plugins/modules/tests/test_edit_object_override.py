# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from ._module_contract_smoke import assert_module_contract


def test_module_contract() -> None:
    assert_module_contract("edit_object_override")

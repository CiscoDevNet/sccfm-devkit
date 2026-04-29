from __future__ import annotations

from ._module_contract_smoke import assert_module_contract


def test_module_contract() -> None:
    assert_module_contract("apply_object_override_as_default")

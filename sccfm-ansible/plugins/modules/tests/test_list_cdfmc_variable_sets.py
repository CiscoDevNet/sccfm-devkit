# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import list_cdfmc_variable_sets

from ._module_contract_smoke import assert_module_contract


def test_module_contract() -> None:
    assert_module_contract("list_cdfmc_variable_sets")


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    return {
        "domain_uid": "domain-1",
        "limit": 200,
        "profile": "default",
    }


@pytest.fixture
def mock_module_instance(base_module_params: dict[str, Any]) -> MagicMock:
    mock_module = MagicMock()
    mock_module.params = base_module_params.copy()
    mock_module.check_mode = False
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


@patch("plugins.modules.list_cdfmc_variable_sets.CdfmcVariableSetService")
@patch("plugins.modules.list_cdfmc_variable_sets.AnsibleModule")
def test_should_list_variable_sets(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    vs = MagicMock()
    vs.uid = "vs-1"
    vs.name = "Default-Set"

    mock_service = MagicMock()
    mock_service.list_variable_sets.return_value = [vs]
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        list_cdfmc_variable_sets.run_module()

    mock_service.list_variable_sets.assert_called_once_with("domain-1", limit=200)
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["variable_sets"] == [{"uid": "vs-1", "name": "Default-Set"}]


def test_build_argument_spec() -> None:
    spec = list_cdfmc_variable_sets.build_argument_spec()
    assert "domain_uid" in spec
    assert "limit" in spec
    assert "profile" in spec
    assert "config_path" in spec

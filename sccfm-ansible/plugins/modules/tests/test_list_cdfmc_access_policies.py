# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import list_cdfmc_access_policies

from ._module_contract_smoke import assert_module_contract


def test_module_contract() -> None:
    assert_module_contract("list_cdfmc_access_policies")


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    return {
        "domain_uid": "domain-1",
        "limit": 5,
        "offset": 5,
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


@patch("plugins.modules.list_cdfmc_access_policies.CdfmcAccessPolicyService")
@patch("plugins.modules.list_cdfmc_access_policies.AnsibleModule")
def test_should_list_access_policies_with_pagination(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    policy = MagicMock()
    policy.uid = "policy-1"
    policy.name = "Default Access Policy"
    page = MagicMock()
    page.items = [policy]
    page.count = 10
    page.limit = 5
    page.offset = 5

    mock_service = MagicMock()
    mock_service.get_access_policies.return_value = page
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        list_cdfmc_access_policies.run_module()

    mock_service.get_access_policies.assert_called_once_with(
        "domain-1",
        limit=5,
        offset=5,
    )
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["access_policies"] == [{"uid": "policy-1", "name": "Default Access Policy"}]
    assert call_kwargs["count"] == 10
    assert call_kwargs["limit"] == 5
    assert call_kwargs["offset"] == 5


@patch("plugins.modules.list_cdfmc_access_policies.CdfmcAccessPolicyService")
@patch("plugins.modules.list_cdfmc_access_policies.AnsibleModule")
def test_should_list_access_policies_in_check_mode(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    policy = MagicMock()
    policy.uid = "policy-1"
    policy.name = "Default Access Policy"
    page = MagicMock()
    page.items = [policy]
    page.count = 10
    page.limit = 5
    page.offset = 5

    mock_service = MagicMock()
    mock_service.get_access_policies.return_value = page
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        list_cdfmc_access_policies.run_module()

    mock_service.get_access_policies.assert_called_once_with(
        "domain-1",
        limit=5,
        offset=5,
    )
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["access_policies"] == [{"uid": "policy-1", "name": "Default Access Policy"}]
    assert call_kwargs["count"] == 10
    assert call_kwargs["limit"] == 5
    assert call_kwargs["offset"] == 5


def test_build_argument_spec() -> None:
    spec = list_cdfmc_access_policies.build_argument_spec()
    assert "domain_uid" in spec
    assert "limit" in spec
    assert "offset" in spec
    assert "profile" in spec
    assert "config_path" in spec

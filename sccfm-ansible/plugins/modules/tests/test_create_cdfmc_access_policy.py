# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import create_cdfmc_access_policy as module_under_test

from ._module_contract_smoke import assert_module_contract


def test_module_contract() -> None:
    assert_module_contract("create_cdfmc_access_policy")


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    return {
        "domain_uid": "domain-1",
        "name": "hydra-vftd-BPR-1-AC",
        "payload": {"defaultAction": {"action": "BLOCK"}},
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


def _mock_policy(uid: str, name: str) -> MagicMock:
    policy = MagicMock()
    policy.uid = uid
    policy.name = name
    return policy


@patch("plugins.modules.create_cdfmc_access_policy.CdfmcAccessPolicyService")
@patch("plugins.modules.create_cdfmc_access_policy.AnsibleModule")
def test_creates_policy_when_it_does_not_exist(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    existing_page = MagicMock()
    existing_page.items = []
    mock_service.get_access_policies.return_value = existing_page
    mock_service.create_access_policy.return_value = _mock_policy(
        "policy-1", "hydra-vftd-BPR-1-AC"
    )
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        module_under_test.run_module()

    mock_service.get_access_policies.assert_called_once_with("domain-1", limit=200)
    mock_service.create_access_policy.assert_called_once_with(
        "domain-1", "hydra-vftd-BPR-1-AC", {"defaultAction": {"action": "BLOCK"}}
    )

    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["access_policy"] == {"uid": "policy-1", "name": "hydra-vftd-BPR-1-AC"}


@patch("plugins.modules.create_cdfmc_access_policy.CdfmcAccessPolicyService")
@patch("plugins.modules.create_cdfmc_access_policy.AnsibleModule")
def test_is_idempotent_when_policy_already_exists(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    existing_page = MagicMock()
    existing_page.items = [_mock_policy("policy-1", "hydra-vftd-BPR-1-AC")]
    mock_service.get_access_policies.return_value = existing_page
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        module_under_test.run_module()

    mock_service.create_access_policy.assert_not_called()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["access_policy"] == {"uid": "policy-1", "name": "hydra-vftd-BPR-1-AC"}


@patch("plugins.modules.create_cdfmc_access_policy.CdfmcAccessPolicyService")
@patch("plugins.modules.create_cdfmc_access_policy.AnsibleModule")
def test_check_mode_does_not_create(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    existing_page = MagicMock()
    existing_page.items = []
    mock_service.get_access_policies.return_value = existing_page
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        module_under_test.run_module()

    mock_service.create_access_policy.assert_not_called()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True


def test_build_argument_spec() -> None:
    spec = module_under_test.build_argument_spec()
    assert "domain_uid" in spec
    assert "name" in spec
    assert "payload" in spec
    assert "profile" in spec
    assert "config_path" in spec

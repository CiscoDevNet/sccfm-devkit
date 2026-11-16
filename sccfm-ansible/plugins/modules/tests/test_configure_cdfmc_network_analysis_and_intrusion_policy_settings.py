# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import (
    configure_cdfmc_network_analysis_and_intrusion_policy_settings as module_under_test,
)

from ._module_contract_smoke import assert_module_contract

_MODULE_PATH = (
    "plugins.modules.configure_cdfmc_network_analysis_and_intrusion_policy_settings"
)


def test_module_contract() -> None:
    assert_module_contract("configure_cdfmc_network_analysis_and_intrusion_policy_settings")


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    return {
        "domain_uid": "domain-1",
        "policy_id": "policy-1",
        "base_ips_policy": {"uid": "ips-1", "name": "Maximum Detection"},
        "base_ips_variable_set": {"uid": "vs-1", "name": "Default-Set"},
        "default_network_analysis_policy": {"uid": "nap-1", "name": "Maximum Detection"},
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


@patch(f"{_MODULE_PATH}.CdfmcNetworkAnalysisAndIntrusionPolicySettingService")
@patch(f"{_MODULE_PATH}.AnsibleModule")
def test_updates_setting_when_refs_differ(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_setting.return_value = {
        "baseInspection": {
            "baseIpsPolicy": {"id": "ips-old"},
            "baseIpsVariableSet": {"id": "vs-1"},
        },
        "networkAnalysis": {"defaultNetworkAnalysisPolicy": {"id": "nap-old"}},
    }
    mock_service.update_setting.return_value = {"id": "setting-1"}
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        module_under_test.run_module()

    mock_service.update_setting.assert_called_once_with(
        "domain-1",
        "policy-1",
        base_ips_policy={"id": "ips-1", "name": "Maximum Detection", "type": "IntrusionPolicy"},
        base_ips_variable_set={"id": "vs-1", "name": "Default-Set", "type": "VariableSet"},
        default_network_analysis_policy={
            "id": "nap-1",
            "name": "Maximum Detection",
            "type": "NetworkAnalysisPolicy",
        },
    )
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["setting"] == {"id": "setting-1"}


@patch(f"{_MODULE_PATH}.CdfmcNetworkAnalysisAndIntrusionPolicySettingService")
@patch(f"{_MODULE_PATH}.AnsibleModule")
def test_is_idempotent_when_refs_already_match(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    existing = {
        "baseInspection": {
            "baseIpsPolicy": {"id": "ips-1"},
            "baseIpsVariableSet": {"id": "vs-1"},
        },
        "networkAnalysis": {"defaultNetworkAnalysisPolicy": {"id": "nap-1"}},
    }
    mock_service.get_setting.return_value = existing
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        module_under_test.run_module()

    mock_service.update_setting.assert_not_called()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["setting"] == existing


@patch(f"{_MODULE_PATH}.CdfmcNetworkAnalysisAndIntrusionPolicySettingService")
@patch(f"{_MODULE_PATH}.AnsibleModule")
def test_check_mode_does_not_update(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_setting.return_value = {
        "baseInspection": {
            "baseIpsPolicy": {"id": "ips-old"},
            "baseIpsVariableSet": {"id": "vs-1"},
        },
        "networkAnalysis": {"defaultNetworkAnalysisPolicy": {"id": "nap-old"}},
    }
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        module_under_test.run_module()

    mock_service.update_setting.assert_not_called()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True


def test_build_argument_spec() -> None:
    spec = module_under_test.build_argument_spec()
    assert "domain_uid" in spec
    assert "policy_id" in spec
    assert "base_ips_policy" in spec
    assert "base_ips_variable_set" in spec
    assert "default_network_analysis_policy" in spec
    assert "profile" in spec
    assert "config_path" in spec

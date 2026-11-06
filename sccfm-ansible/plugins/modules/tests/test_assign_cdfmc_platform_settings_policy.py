# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import assign_cdfmc_platform_settings_policy as module_under_test

from ._module_contract_smoke import assert_module_contract


def test_module_contract() -> None:
    assert_module_contract("assign_cdfmc_platform_settings_policy")


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    return {
        "domain_uid": "domain-1",
        "policy_name": "Lab Platform Settings",
        "device_name": "vftd-a",
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


@patch(
    "plugins.modules.assign_cdfmc_platform_settings_policy."
    "CdfmcPlatformSettingsPolicyService"
)
@patch("plugins.modules.assign_cdfmc_platform_settings_policy.AnsibleModule")
def test_assigns_policy_to_device(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_policy_uid_by_name.return_value = "policy-1"
    mock_service.get_fmc_device_id.return_value = "device-1"

    result = MagicMock()
    result.assignment_id = "assignment-1"
    result.policy_uid = "policy-1"
    result.policy_name = "Lab Platform Settings"
    result.device_id = "device-1"
    result.target_ids = ["device-1"]
    result.already_assigned = False
    mock_service.assign_policy_to_device.return_value = result
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        module_under_test.run_module()

    mock_service.get_policy_uid_by_name.assert_called_once_with(
        "domain-1", "Lab Platform Settings"
    )
    mock_service.get_fmc_device_id.assert_called_once_with("domain-1", "vftd-a")
    mock_service.assign_policy_to_device.assert_called_once_with(
        "domain-1", "policy-1", "Lab Platform Settings", "device-1"
    )

    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["assignment"]["assignment_id"] == "assignment-1"
    assert call_kwargs["assignment"]["already_assigned"] is False


@patch(
    "plugins.modules.assign_cdfmc_platform_settings_policy."
    "CdfmcPlatformSettingsPolicyService"
)
@patch("plugins.modules.assign_cdfmc_platform_settings_policy.AnsibleModule")
def test_is_idempotent_when_already_assigned(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_policy_uid_by_name.return_value = "policy-1"
    mock_service.get_fmc_device_id.return_value = "device-1"

    result = MagicMock()
    result.assignment_id = "assignment-1"
    result.policy_uid = "policy-1"
    result.policy_name = "Lab Platform Settings"
    result.device_id = "device-1"
    result.target_ids = ["device-1"]
    result.already_assigned = True
    mock_service.assign_policy_to_device.return_value = result
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        module_under_test.run_module()

    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["assignment"]["already_assigned"] is True


@patch(
    "plugins.modules.assign_cdfmc_platform_settings_policy."
    "CdfmcPlatformSettingsPolicyService"
)
@patch("plugins.modules.assign_cdfmc_platform_settings_policy.AnsibleModule")
def test_check_mode_does_not_assign(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_policy_uid_by_name.return_value = "policy-1"
    mock_service.get_fmc_device_id.return_value = "device-1"
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        module_under_test.run_module()

    mock_service.assign_policy_to_device.assert_not_called()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True


@patch(
    "plugins.modules.assign_cdfmc_platform_settings_policy."
    "CdfmcPlatformSettingsPolicyService"
)
@patch("plugins.modules.assign_cdfmc_platform_settings_policy.AnsibleModule")
def test_fails_cleanly_when_policy_name_not_found(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_policy_uid_by_name.side_effect = ValueError(
        "Platform settings policy 'Lab Platform Settings' not found"
    )
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        module_under_test.run_module()

    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "not found" in call_kwargs["msg"]


def test_build_argument_spec() -> None:
    spec = module_under_test.build_argument_spec()
    assert "domain_uid" in spec
    assert "policy_name" in spec
    assert "device_name" in spec
    assert "profile" in spec
    assert "config_path" in spec

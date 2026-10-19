# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import create_access_rule  # noqa: E402


@pytest.fixture
def sample_access_rule_response() -> MagicMock:
    response = MagicMock()
    response.to_dict.return_value = {
        "uid": "rule-uid-123",
        "access_group_uid": "ag-uid-001",
        "entity_uid": "device-uid-001",
        "index": 1,
        "rule_action": "PERMIT",
        "remark": "Allow web traffic",
        "source_network": {"name": "web-servers", "uid": "net-uid-001"},
        "destination_network": {"name": "db-servers", "uid": "net-uid-002"},
    }
    return response


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    return {
        "access_group_uid": "ag-uid-001",
        "entity_uid": "device-uid-001",
        "index": 1,
        "rule_action": "PERMIT",
        "remark": "Allow web traffic",
        "source_network": "web-servers",
        "destination_network": "db-servers",
        "protocol": "tcp",
        "source_port": None,
        "destination_port": "443",
        "log_level": None,
        "log_interval": None,
        "active": True,
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


@patch("plugins.modules.create_access_rule.Config")
@patch("plugins.modules.create_access_rule.AccessRuleService")
@patch("plugins.modules.create_access_rule.AnsibleModule")
def test_should_create_access_rule_successfully(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_access_rule_response: MagicMock,
) -> None:
    """run_module should create an access rule and return changed=True."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.create_access_rule.return_value = sample_access_rule_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_access_rule.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["access_rule"]["uid"] == "rule-uid-123"
    assert "Successfully created" in call_kwargs["msg"]


@patch("plugins.modules.create_access_rule.Config")
@patch("plugins.modules.create_access_rule.AccessRuleService")
@patch("plugins.modules.create_access_rule.AnsibleModule")
def test_should_create_access_rule_without_optional_fields(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_access_rule_response: MagicMock,
) -> None:
    """run_module should create a rule even when optional fields are omitted."""
    mock_module_instance.params = {
        "access_group_uid": "ag-uid-001",
        "entity_uid": "device-uid-001",
        "index": 1,
        "rule_action": "PERMIT",
        "remark": None,
        "source_network": None,
        "destination_network": None,
        "protocol": None,
        "source_port": None,
        "destination_port": None,
        "log_level": None,
        "log_interval": None,
        "active": None,
        "profile": "default",
    }
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.create_access_rule.return_value = sample_access_rule_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_access_rule.run_module()

    mock_service.create_access_rule.assert_called_once()
    mock_module_instance.exit_json.assert_called_once()
    assert mock_module_instance.exit_json.call_args[1]["changed"] is True


@patch("plugins.modules.create_access_rule.Config")
@patch("plugins.modules.create_access_rule.AccessRuleService")
@patch("plugins.modules.create_access_rule.AnsibleModule")
def test_should_pass_all_parameters_to_service(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_access_rule_response: MagicMock,
) -> None:
    """run_module should pass all parameters correctly to the service."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.create_access_rule.return_value = sample_access_rule_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_access_rule.run_module()

    mock_service.create_access_rule.assert_called_once_with(
        access_group_uid="ag-uid-001",
        entity_uid="device-uid-001",
        index=1,
        rule_action="PERMIT",
        remark="Allow web traffic",
        source_network="web-servers",
        destination_network="db-servers",
        protocol="tcp",
        source_port=None,
        destination_port="443",
        log_level=None,
        log_interval=None,
        active=True,
    )


@patch("plugins.modules.create_access_rule.Config")
@patch("plugins.modules.create_access_rule.AccessRuleService")
@patch("plugins.modules.create_access_rule.AnsibleModule")
def test_should_return_check_mode_without_creating(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should return changed=True in check mode without calling the API."""
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_access_rule.run_module()

    mock_service.create_access_rule.assert_not_called()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert "Would create" in call_kwargs["msg"]


@patch("plugins.modules.create_access_rule.Config")
@patch("plugins.modules.create_access_rule.AccessRuleService")
@patch("plugins.modules.create_access_rule.AnsibleModule")
def test_should_fail_if_service_raises_exception(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail with error message when service layer raises."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.create_access_rule.side_effect = Exception("API error: 400")
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_access_rule.run_module()

    mock_module_instance.fail_json.assert_called_once()
    assert "API error: 400" in mock_module_instance.fail_json.call_args[1]["msg"]


def test_build_argument_spec() -> None:
    """build_argument_spec should include all expected keys."""
    spec = create_access_rule.build_argument_spec()
    assert "access_group_uid" in spec
    assert "entity_uid" in spec
    assert "index" in spec
    assert "rule_action" in spec
    assert "source_network" in spec
    assert "destination_network" in spec
    assert "protocol" in spec
    assert "profile" in spec
    assert "config_path" in spec

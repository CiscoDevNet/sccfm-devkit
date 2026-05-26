# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import update_access_rule  # noqa: E402


@pytest.fixture
def sample_access_rule_response() -> MagicMock:
    response = MagicMock()
    response.to_dict.return_value = {
        "uid": "rule-uid-123",
        "access_group_uid": "ag-uid-001",
        "entity_uid": "device-uid-001",
        "index": 1,
        "rule_action": "DENY",
        "remark": "Updated remark",
        "source_network": {"name": "web-servers", "uid": "net-uid-001"},
        "destination_network": {"name": "db-servers", "uid": "net-uid-002"},
    }
    return response


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    return {
        "uid": "rule-uid-123",
        "index": None,
        "rule_action": "DENY",
        "remark": "Updated remark",
        "source_network": None,
        "destination_network": None,
        "protocol": None,
        "source_port": None,
        "destination_port": None,
        "log_level": None,
        "log_interval": None,
        "active": None,
        "region": "us",
        "api_token": "test-token-123",
    }


@pytest.fixture
def mock_module_instance(base_module_params: dict[str, Any]) -> MagicMock:
    mock_module = MagicMock()
    mock_module.params = base_module_params.copy()
    mock_module.check_mode = False
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


@patch("plugins.modules.update_access_rule.Config")
@patch("plugins.modules.update_access_rule.AccessRuleService")
@patch("plugins.modules.update_access_rule.AnsibleModule")
def test_should_update_access_rule_successfully(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_access_rule_response: MagicMock,
) -> None:
    """run_module should update an access rule and return changed=True."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.modify_access_rule.return_value = sample_access_rule_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_access_rule.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["access_rule"]["uid"] == "rule-uid-123"
    assert "Successfully updated" in call_kwargs["msg"]


@patch("plugins.modules.update_access_rule.Config")
@patch("plugins.modules.update_access_rule.AccessRuleService")
@patch("plugins.modules.update_access_rule.AnsibleModule")
def test_should_return_check_mode_without_updating(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should return changed=True in check mode without calling API."""
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_access_rule.run_module()

    mock_service.modify_access_rule.assert_not_called()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert "Would update" in call_kwargs["msg"]


@patch("plugins.modules.update_access_rule.AnsibleModule")
def test_should_fail_without_update_fields(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail when no update field is provided."""
    mock_module_instance.params = {
        "uid": "rule-uid-123",
        "index": None,
        "rule_action": None,
        "remark": None,
        "source_network": None,
        "destination_network": None,
        "protocol": None,
        "source_port": None,
        "destination_port": None,
        "log_level": None,
        "log_interval": None,
        "active": None,
        "region": "us",
        "api_token": "test-token-123",
    }
    mock_ansible_module_class.return_value = mock_module_instance

    with pytest.raises(SystemExit):
        update_access_rule.run_module()

    mock_module_instance.fail_json.assert_called_once()
    assert "At least one update field" in mock_module_instance.fail_json.call_args[1]["msg"]


@patch("plugins.modules.update_access_rule.Config")
@patch("plugins.modules.update_access_rule.AccessRuleService")
@patch("plugins.modules.update_access_rule.AnsibleModule")
def test_should_fail_on_api_error(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail with error message when service raises."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.modify_access_rule.side_effect = Exception("API error: 400")
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_access_rule.run_module()

    mock_module_instance.fail_json.assert_called_once()
    assert "API error: 400" in mock_module_instance.fail_json.call_args[1]["msg"]


def test_build_argument_spec() -> None:
    """build_argument_spec should include all expected keys."""
    spec = update_access_rule.build_argument_spec()
    assert "uid" in spec
    assert "index" in spec
    assert "rule_action" in spec
    assert "remark" in spec
    assert "source_network" in spec
    assert "destination_network" in spec
    assert "protocol" in spec
    assert "region" in spec
    assert "api_token" in spec

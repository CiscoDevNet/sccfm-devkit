# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import delete_access_rule  # noqa: E402

from cisco_sccfm_core.errors import NotFoundError


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    return {
        "uid": "rule-uid-123",
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


@patch("plugins.modules.delete_access_rule.Config")
@patch("plugins.modules.delete_access_rule.AccessRuleService")
@patch("plugins.modules.delete_access_rule.AnsibleModule")
def test_should_delete_access_rule_successfully(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should delete an access rule and return changed=True."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.delete_access_rule.return_value = "rule-uid-123"
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        delete_access_rule.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["deleted_uid"] == "rule-uid-123"
    assert "Successfully deleted" in call_kwargs["msg"]


@patch("plugins.modules.delete_access_rule.Config")
@patch("plugins.modules.delete_access_rule.AccessRuleService")
@patch("plugins.modules.delete_access_rule.AnsibleModule")
def test_should_return_check_mode_without_deleting(
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
        delete_access_rule.run_module()

    mock_service.delete_access_rule.assert_not_called()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert "Would delete" in call_kwargs["msg"]


@patch("plugins.modules.delete_access_rule.Config")
@patch("plugins.modules.delete_access_rule.AccessRuleService")
@patch("plugins.modules.delete_access_rule.AnsibleModule")
def test_should_return_not_changed_when_not_found(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should return changed=False when rule does not exist."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.delete_access_rule.side_effect = NotFoundError("Not found")
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        delete_access_rule.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["deleted_uid"] is None


@patch("plugins.modules.delete_access_rule.Config")
@patch("plugins.modules.delete_access_rule.AccessRuleService")
@patch("plugins.modules.delete_access_rule.AnsibleModule")
def test_should_fail_on_api_error(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail with error message when service raises non-NotFoundError."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.delete_access_rule.side_effect = Exception("API error: 500")
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        delete_access_rule.run_module()

    mock_module_instance.fail_json.assert_called_once()
    assert "API error: 500" in mock_module_instance.fail_json.call_args[1]["msg"]


def test_build_argument_spec() -> None:
    """build_argument_spec should include required keys."""
    spec = delete_access_rule.build_argument_spec()
    assert "uid" in spec
    assert "profile" in spec
    assert "config_path" in spec

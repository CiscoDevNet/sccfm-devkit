from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import list_access_rules  # noqa: E402


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    return {
        "query": None,
        "limit": 50,
        "offset": 0,
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


@patch("plugins.modules.list_access_rules.Config")
@patch("plugins.modules.list_access_rules.AccessRuleService")
@patch("plugins.modules.list_access_rules.AnsibleModule")
def test_should_list_access_rules_successfully(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should list access rules and return changed=False."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_result = MagicMock()
    mock_result.items = [MagicMock(), MagicMock()]
    mock_result.items[0].to_dict.return_value = {"uid": "rule-1", "rule_action": "PERMIT"}
    mock_result.items[1].to_dict.return_value = {"uid": "rule-2", "rule_action": "DENY"}
    mock_result.count = 2
    mock_result.limit = 50
    mock_result.offset = 0

    mock_service = MagicMock()
    mock_service.list_access_rules.return_value = mock_result
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        list_access_rules.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert len(call_kwargs["access_rules"]) == 2
    assert call_kwargs["count"] == 2


@patch("plugins.modules.list_access_rules.AnsibleModule")
def test_should_return_empty_in_check_mode(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should return empty list in check mode."""
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    with pytest.raises(SystemExit):
        list_access_rules.run_module()

    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["access_rules"] == []
    assert call_kwargs["count"] == 0


@patch("plugins.modules.list_access_rules.Config")
@patch("plugins.modules.list_access_rules.AccessRuleService")
@patch("plugins.modules.list_access_rules.AnsibleModule")
def test_should_fail_on_api_error(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail with error message when service raises."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.list_access_rules.side_effect = Exception("API error")
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        list_access_rules.run_module()

    mock_module_instance.fail_json.assert_called_once()
    assert "API error" in mock_module_instance.fail_json.call_args[1]["msg"]


def test_build_argument_spec() -> None:
    """build_argument_spec should include expected keys."""
    spec = list_access_rules.build_argument_spec()
    assert "query" in spec
    assert "limit" in spec
    assert "offset" in spec
    assert "region" in spec
    assert "api_token" in spec

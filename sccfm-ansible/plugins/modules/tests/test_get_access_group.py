from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import get_access_group  # noqa: E402


@pytest.fixture
def sample_access_group_response() -> MagicMock:
    response = MagicMock()
    response.to_dict.return_value = {
        "uid": "ag-uid-123",
        "name": "outside_access_in",
        "entity_uid": "device-uid-456",
        "is_shared": False,
    }
    return response


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    return {
        "uid": "ag-uid-123",
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


@patch("plugins.modules.get_access_group.Config")
@patch("plugins.modules.get_access_group.AccessGroupService")
@patch("plugins.modules.get_access_group.AnsibleModule")
def test_should_get_access_group_successfully(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_access_group_response: MagicMock,
) -> None:
    """run_module should fetch an access group and return changed=False."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.fetch_access_group.return_value = sample_access_group_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        get_access_group.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["access_group"]["uid"] == "ag-uid-123"


@patch("plugins.modules.get_access_group.Config")
@patch("plugins.modules.get_access_group.AccessGroupService")
@patch("plugins.modules.get_access_group.AnsibleModule")
def test_should_fetch_access_group_in_check_mode(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """Read-only modules should fetch the object in check mode."""
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    response = MagicMock()
    response.to_dict.return_value = {"uid": "ag-uid-123", "name": "outside_access_in"}
    mock_service.fetch_access_group.return_value = response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        get_access_group.run_module()

    mock_service.fetch_access_group.assert_called_once_with(uid="ag-uid-123")
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["access_group"] == {"uid": "ag-uid-123", "name": "outside_access_in"}


@patch("plugins.modules.get_access_group.Config")
@patch("plugins.modules.get_access_group.AccessGroupService")
@patch("plugins.modules.get_access_group.AnsibleModule")
def test_should_fail_on_api_error(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail with error message when service raises."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.fetch_access_group.side_effect = Exception("API error: 404")
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        get_access_group.run_module()

    mock_module_instance.fail_json.assert_called_once()
    assert "API error: 404" in mock_module_instance.fail_json.call_args[1]["msg"]


def test_build_argument_spec() -> None:
    """build_argument_spec should include required keys."""
    spec = get_access_group.build_argument_spec()
    assert "uid" in spec
    assert "region" in spec
    assert "api_token" in spec

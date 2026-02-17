from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import list_network_objects  # noqa: E402


@pytest.fixture
def sample_list_response() -> MagicMock:
    """Provides a sample NetworkObjectListResponse for testing."""
    response = MagicMock()
    response.count = 2
    response.limit = 50
    response.offset = 0

    obj1 = MagicMock()
    obj1.to_dict.return_value = {
        "uid": "uid-001",
        "name": "web-server",
        "description": "Web server host",
        "elements": [],
        "labels": ["production"],
        "tags": {},
        "object_type": "NETWORK_OBJECT",
        "literal": "10.0.1.100",
    }

    obj2 = MagicMock()
    obj2.to_dict.return_value = {
        "uid": "uid-002",
        "name": "app-subnet",
        "description": "Application subnet",
        "elements": [],
        "labels": ["staging"],
        "tags": {"env": ["staging"]},
        "object_type": "NETWORK_GROUP",
        "literal": "10.0.2.0/24",
    }

    response.items = [obj1, obj2]
    return response


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    """Provides base module parameters."""
    return {
        "query": None,
        "limit": 50,
        "offset": 0,
        "region": "us",
        "api_token": "test-token-123",
    }


@pytest.fixture
def mock_module_instance(base_module_params: dict[str, Any]) -> MagicMock:
    """Creates a mock module instance with exit_json/fail_json that raise SystemExit."""
    mock_module = MagicMock()
    mock_module.params = base_module_params.copy()
    mock_module.check_mode = False
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


@patch("plugins.modules.list_network_objects.Config")
@patch("plugins.modules.list_network_objects.NetworkObjectService")
@patch("plugins.modules.list_network_objects.AnsibleModule")
def test_should_list_network_objects_successfully(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_list_response: MagicMock,
) -> None:
    """run_module should list network objects and return changed=False."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.list_network_objects.return_value = sample_list_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        list_network_objects.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["count"] == 2
    assert len(call_kwargs["network_objects"]) == 2
    assert call_kwargs["network_objects"][0]["name"] == "web-server"
    assert call_kwargs["network_objects"][1]["name"] == "app-subnet"


@patch("plugins.modules.list_network_objects.Config")
@patch("plugins.modules.list_network_objects.NetworkObjectService")
@patch("plugins.modules.list_network_objects.AnsibleModule")
def test_should_forward_query_and_pagination(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_list_response: MagicMock,
) -> None:
    """run_module should forward query, limit, and offset to the service."""
    mock_module_instance.params = {
        "query": "name:web*",
        "limit": 10,
        "offset": 20,
        "region": "eu",
        "api_token": "test-token-456",
    }
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.list_network_objects.return_value = sample_list_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        list_network_objects.run_module()

    mock_service.list_network_objects.assert_called_once_with(
        limit=10,
        offset=20,
        query="name:web*",
    )


@patch("plugins.modules.list_network_objects.Config")
@patch("plugins.modules.list_network_objects.NetworkObjectService")
@patch("plugins.modules.list_network_objects.AnsibleModule")
def test_should_fail_if_service_raises_exception(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail with error message when service layer raises."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.list_network_objects.side_effect = Exception("API error: 500")
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        list_network_objects.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "API error: 500" in call_kwargs["msg"]


@patch("plugins.modules.list_network_objects.AnsibleModule")
def test_should_fail_if_region_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail when region is not provided."""
    del mock_module_instance.params["region"]
    mock_ansible_module_class.return_value = mock_module_instance

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            list_network_objects.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "region is required" in call_kwargs["msg"]


@patch("plugins.modules.list_network_objects.AnsibleModule")
def test_should_fail_if_api_token_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail when api_token is not provided."""
    del mock_module_instance.params["api_token"]
    mock_ansible_module_class.return_value = mock_module_instance

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            list_network_objects.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "api_token is required" in call_kwargs["msg"]


@patch("plugins.modules.list_network_objects.AnsibleModule")
def test_should_support_check_mode(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should return empty results in check mode without calling the API."""
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    with pytest.raises(SystemExit):
        list_network_objects.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["network_objects"] == []
    assert call_kwargs["count"] == 0

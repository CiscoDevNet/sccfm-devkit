from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import create_network_group  # noqa: E402


@pytest.fixture
def sample_network_group_response() -> MagicMock:
    """Provides a sample NetworkGroupResponse for testing."""
    response = MagicMock()
    response.to_dict.return_value = {
        "uid": "net-grp-uid-456",
        "name": "test-network-group",
        "description": "Test network group description",
        "elements": [],
        "labels": ["production", "web"],
        "tags": {"environment": ["production"]},
        "object_type": "NETWORK_GROUP",
        "literals": ["10.0.1.100", "10.0.1.101"],
        "referenced_object_uids": ["ref-uid-001"],
    }
    return response


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    """Provides base module parameters."""
    return {
        "name": "test-network-group",
        "network_literals": ["10.0.1.100", "10.0.1.101"],
        "url_literals": None,
        "referenced_objects": ["web-server-01"],
        "description": "Test network group description",
        "labels": ["production", "web"],
        "tags": {"environment": ["production"]},
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


@patch("plugins.modules.create_network_group.Config")
@patch("plugins.modules.create_network_group.NetworkGroupService")
@patch("plugins.modules.create_network_group.AnsibleModule")
def test_should_create_network_group_successfully(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_network_group_response: MagicMock,
) -> None:
    """run_module should create a network group and return changed=True."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = None
    mock_service.create_network_group.return_value = sample_network_group_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_group.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["network_group"]["uid"] == "net-grp-uid-456"
    assert call_kwargs["network_group"]["name"] == "test-network-group"
    assert "Successfully created" in call_kwargs["msg"]


@patch("plugins.modules.create_network_group.Config")
@patch("plugins.modules.create_network_group.NetworkGroupService")
@patch("plugins.modules.create_network_group.AnsibleModule")
def test_should_create_network_group_without_optional_fields(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_network_group_response: MagicMock,
) -> None:
    """run_module should create a network group even when optional fields are omitted."""
    mock_module_instance.params = {
        "name": "minimal-group",
        "network_literals": ["10.0.0.1"],
        "url_literals": None,
        "referenced_objects": None,
        "description": None,
        "labels": None,
        "tags": None,
        "region": "us",
        "api_token": "test-token-123",
    }
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = None
    mock_service.create_network_group.return_value = sample_network_group_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_group.run_module()

    mock_service.create_network_group.assert_called_once_with(
        name="minimal-group",
        network_literals=["10.0.0.1"],
        url_literals=None,
        referenced_objects=None,
        description=None,
        labels=None,
        tags=None,
    )
    mock_module_instance.exit_json.assert_called_once()
    assert mock_module_instance.exit_json.call_args[1]["changed"] is True


@patch("plugins.modules.create_network_group.Config")
@patch("plugins.modules.create_network_group.NetworkGroupService")
@patch("plugins.modules.create_network_group.AnsibleModule")
def test_should_fail_if_service_raises_exception(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail with error message when service layer raises."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = None
    mock_service.create_network_group.side_effect = Exception("API error: 409 Conflict")
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_group.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "API error: 409 Conflict" in call_kwargs["msg"]


@patch("plugins.modules.create_network_group.AnsibleModule")
def test_should_fail_if_region_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail when region is not provided."""
    del mock_module_instance.params["region"]
    mock_ansible_module_class.return_value = mock_module_instance

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            create_network_group.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "region is required" in call_kwargs["msg"]


@patch("plugins.modules.create_network_group.AnsibleModule")
def test_should_fail_if_api_token_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail when api_token is not provided."""
    del mock_module_instance.params["api_token"]
    mock_ansible_module_class.return_value = mock_module_instance

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            create_network_group.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "api_token is required" in call_kwargs["msg"]


@patch("plugins.modules.create_network_group.Config")
@patch("plugins.modules.create_network_group.NetworkGroupService")
@patch("plugins.modules.create_network_group.AnsibleModule")
def test_should_pass_all_parameters_to_service(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_network_group_response: MagicMock,
) -> None:
    """run_module should pass all parameters correctly to the service."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = None
    mock_service.create_network_group.return_value = sample_network_group_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_group.run_module()

    mock_service.create_network_group.assert_called_once_with(
        name="test-network-group",
        network_literals=["10.0.1.100", "10.0.1.101"],
        url_literals=None,
        referenced_objects=["web-server-01"],
        description="Test network group description",
        labels=["production", "web"],
        tags={"environment": ["production"]},
    )


@patch("plugins.modules.create_network_group.Config")
@patch("plugins.modules.create_network_group.NetworkGroupService")
@patch("plugins.modules.create_network_group.AnsibleModule")
def test_should_create_group_with_url_literals(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_network_group_response: MagicMock,
) -> None:
    """run_module should pass url_literals when network_literals is not set."""
    mock_module_instance.params = {
        "name": "url-group",
        "network_literals": None,
        "url_literals": ["https://example.com"],
        "referenced_objects": None,
        "description": None,
        "labels": None,
        "tags": None,
        "region": "us",
        "api_token": "test-token-123",
    }
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = None
    mock_service.create_network_group.return_value = sample_network_group_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_group.run_module()

    mock_service.create_network_group.assert_called_once_with(
        name="url-group",
        network_literals=None,
        url_literals=["https://example.com"],
        referenced_objects=None,
        description=None,
        labels=None,
        tags=None,
    )
    mock_module_instance.exit_json.assert_called_once()


@patch("plugins.modules.create_network_group.Config")
@patch("plugins.modules.create_network_group.NetworkGroupService")
@patch("plugins.modules.create_network_group.AnsibleModule")
def test_should_support_check_mode(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should return changed=True in check mode without creating."""
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = None
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_group.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert "Would create" in call_kwargs["msg"]
    mock_service.create_network_group.assert_not_called()


@patch("plugins.modules.create_network_group.Config")
@patch("plugins.modules.create_network_group.NetworkGroupService")
@patch("plugins.modules.create_network_group.AnsibleModule")
def test_should_return_unchanged_when_group_already_exists(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_network_group_response: MagicMock,
) -> None:
    """run_module should return changed=False when group already exists."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = sample_network_group_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_group.run_module()

    mock_service.create_network_group.assert_not_called()
    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert "already exists" in call_kwargs["msg"]
    assert call_kwargs["network_group"]["uid"] == "net-grp-uid-456"

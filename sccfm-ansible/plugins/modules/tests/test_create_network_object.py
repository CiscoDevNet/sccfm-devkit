# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import create_network_object  # noqa: E402


@pytest.fixture
def sample_network_object_response() -> MagicMock:
    """Provides a sample NetworkObjectResponse for testing."""
    response = MagicMock()
    response.to_dict.return_value = {
        "uid": "net-obj-uid-123",
        "name": "test-network-object",
        "description": "Test network object description",
        "elements": [],
        "labels": ["production", "web"],
        "tags": {"environment": ["production"]},
        "object_type": "NETWORK_OBJECT",
        "literal": "10.0.1.100",
    }
    return response


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    """Provides base module parameters."""
    return {
        "name": "test-network-object",
        "value": "10.0.1.100",
        "description": "Test network object description",
        "labels": ["production", "web"],
        "tags": {"environment": ["production"]},
        "profile": "default",
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


@patch("plugins.modules.create_network_object.Config")
@patch("plugins.modules.create_network_object.NetworkObjectService")
@patch("plugins.modules.create_network_object.AnsibleModule")
def test_should_create_network_object_successfully(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_network_object_response: MagicMock,
) -> None:
    """run_module should create a network object and return changed=True."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_object_by_name.return_value = None
    mock_service.create_network_object.return_value = sample_network_object_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_object.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["network_object"]["uid"] == "net-obj-uid-123"
    assert call_kwargs["network_object"]["name"] == "test-network-object"
    assert "Successfully created" in call_kwargs["msg"]


@patch("plugins.modules.create_network_object.Config")
@patch("plugins.modules.create_network_object.NetworkObjectService")
@patch("plugins.modules.create_network_object.AnsibleModule")
def test_should_create_network_object_without_optional_fields(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_network_object_response: MagicMock,
) -> None:
    """run_module should create a network object even when optional fields are omitted."""
    mock_module_instance.params = {
        "name": "minimal-object",
        "value": "10.0.0.0/24",
        "description": None,
        "labels": None,
        "tags": None,
        "profile": "default",
    }
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_object_by_name.return_value = None
    mock_service.create_network_object.return_value = sample_network_object_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_object.run_module()

    mock_service.create_network_object.assert_called_once_with(
        name="minimal-object",
        value="10.0.0.0/24",
        description=None,
        labels=None,
        tags=None,
    )
    mock_module_instance.exit_json.assert_called_once()
    assert mock_module_instance.exit_json.call_args[1]["changed"] is True


@patch("plugins.modules.create_network_object.Config")
@patch("plugins.modules.create_network_object.NetworkObjectService")
@patch("plugins.modules.create_network_object.AnsibleModule")
def test_should_fail_if_service_raises_exception(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail with error message when service layer raises."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_object_by_name.return_value = None
    mock_service.create_network_object.side_effect = Exception("API error: 409 Conflict")
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_object.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "API error: 409 Conflict" in call_kwargs["msg"]


@patch("plugins.modules.create_network_object.Config")
@patch("plugins.modules.create_network_object.NetworkObjectService")
@patch("plugins.modules.create_network_object.AnsibleModule")
def test_should_pass_all_parameters_to_service(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_network_object_response: MagicMock,
) -> None:
    """run_module should pass all parameters correctly to the service."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_object_by_name.return_value = None
    mock_service.create_network_object.return_value = sample_network_object_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_object.run_module()

    mock_service.create_network_object.assert_called_once_with(
        name="test-network-object",
        value="10.0.1.100",
        description="Test network object description",
        labels=["production", "web"],
        tags={"environment": ["production"]},
    )


@patch("plugins.modules.create_network_object.Config")
@patch("plugins.modules.create_network_object.NetworkObjectService")
@patch("plugins.modules.create_network_object.AnsibleModule")
def test_should_return_unchanged_if_object_exists_with_same_value(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_network_object_response: MagicMock,
) -> None:
    """run_module should return changed=False if object exists with same value."""
    mock_ansible_module_class.return_value = mock_module_instance

    existing_object = MagicMock()
    existing_object.literal = "10.0.1.100"  # Same value as in params
    existing_object.to_dict.return_value = sample_network_object_response.to_dict.return_value

    mock_service = MagicMock()
    mock_service.get_network_object_by_name.return_value = existing_object
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_object.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert "already exists" in call_kwargs["msg"]
    mock_service.create_network_object.assert_not_called()


@patch("plugins.modules.create_network_object.Config")
@patch("plugins.modules.create_network_object.NetworkObjectService")
@patch("plugins.modules.create_network_object.AnsibleModule")
def test_should_not_create_if_object_exists_with_different_value(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should return unchanged if object exists with different value."""
    mock_ansible_module_class.return_value = mock_module_instance

    existing_object = MagicMock()
    existing_object.literal = "192.168.1.1"  # Different value than in params

    mock_service = MagicMock()
    mock_service.get_network_object_by_name.return_value = existing_object
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_object.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert "already exists" in call_kwargs["msg"]
    mock_service.create_network_object.assert_not_called()


@patch("plugins.modules.create_network_object.Config")
@patch("plugins.modules.create_network_object.NetworkObjectService")
@patch("plugins.modules.create_network_object.AnsibleModule")
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
    mock_service.get_network_object_by_name.return_value = None
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        create_network_object.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert "Would create" in call_kwargs["msg"]
    mock_service.create_network_object.assert_not_called()

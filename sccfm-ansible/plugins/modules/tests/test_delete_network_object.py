# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import delete_network_object  # noqa: E402
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import NotFoundError


@pytest.fixture
def base_module_params_with_uid() -> dict[str, Any]:
    """Provides base module parameters with UID."""
    return {
        "uid": "net-obj-uid-123",
        "name": None,
        "profile": "default",
    }


@pytest.fixture
def base_module_params_with_name() -> dict[str, Any]:
    """Provides base module parameters with name."""
    return {
        "uid": None,
        "name": "test-network-object",
        "profile": "default",
    }


@pytest.fixture
def mock_module_instance(base_module_params_with_uid: dict[str, Any]) -> MagicMock:
    """Creates a mock module instance with exit_json/fail_json that raise SystemExit."""
    mock_module = MagicMock()
    mock_module.params = base_module_params_with_uid.copy()
    mock_module.check_mode = False
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


@patch("plugins.modules.delete_network_object.Config")
@patch("plugins.modules.delete_network_object.NetworkObjectService")
@patch("plugins.modules.delete_network_object.AnsibleModule")
def test_should_delete_network_object_by_uid(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should delete a network object by UID and return changed=True."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.delete_network_object.return_value = "net-obj-uid-123"
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        delete_network_object.run_module()

    mock_service.delete_network_object.assert_called_once_with(uid="net-obj-uid-123", name=None)
    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["deleted_uid"] == "net-obj-uid-123"
    assert "Successfully deleted" in call_kwargs["msg"]
    assert "UID" in call_kwargs["msg"]


@patch("plugins.modules.delete_network_object.Config")
@patch("plugins.modules.delete_network_object.NetworkObjectService")
@patch("plugins.modules.delete_network_object.AnsibleModule")
def test_should_delete_network_object_by_name(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    base_module_params_with_name: dict[str, Any],
) -> None:
    """run_module should delete a network object by name and return changed=True."""
    mock_module_instance.params = base_module_params_with_name
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.delete_network_object.return_value = "net-obj-uid-456"
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        delete_network_object.run_module()

    mock_service.delete_network_object.assert_called_once_with(uid=None, name="test-network-object")
    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["deleted_uid"] == "net-obj-uid-456"
    assert "Successfully deleted" in call_kwargs["msg"]
    assert "name" in call_kwargs["msg"]


@patch("plugins.modules.delete_network_object.Config")
@patch("plugins.modules.delete_network_object.NetworkObjectService")
@patch("plugins.modules.delete_network_object.AnsibleModule")
def test_should_succeed_with_changed_false_when_object_not_found(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    base_module_params_with_name: dict[str, Any],
) -> None:
    """run_module should return changed=False when object is not found (idempotent)."""
    mock_module_instance.params = base_module_params_with_name
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.delete_network_object.side_effect = NotFoundError(
        "Network object with name 'test-network-object' not found."
    )
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        delete_network_object.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert "not found" in call_kwargs["msg"]
    assert call_kwargs["deleted_uid"] is None


@patch("plugins.modules.delete_network_object.Config")
@patch("plugins.modules.delete_network_object.NetworkObjectService")
@patch("plugins.modules.delete_network_object.AnsibleModule")
def test_should_fail_on_invalid_parameters(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail when service raises ValueError."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.delete_network_object.side_effect = ValueError(
        "Either 'uid' or 'name' must be provided."
    )
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        delete_network_object.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "Invalid parameters" in call_kwargs["msg"]


@patch("plugins.modules.delete_network_object.Config")
@patch("plugins.modules.delete_network_object.NetworkObjectService")
@patch("plugins.modules.delete_network_object.AnsibleModule")
def test_should_fail_on_generic_exception(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail with error message when service layer raises generic exception."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.delete_network_object.side_effect = Exception(
        "API error: 500 Internal Server Error"
    )
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        delete_network_object.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "Failed to delete network object" in call_kwargs["msg"]
    assert "500 Internal Server Error" in call_kwargs["msg"]


@patch("plugins.modules.delete_network_object.Config")
@patch("plugins.modules.delete_network_object.NetworkObjectService")
@patch("plugins.modules.delete_network_object.AnsibleModule")
def test_should_return_structured_api_error(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should return structured error info when ApiException occurs."""
    mock_ansible_module_class.return_value = mock_module_instance

    api_error = ApiException(status=403, reason="Forbidden")
    api_error.body = (
        '{"errorMsg": "Access denied", "errorCode": "FORBIDDEN", '
        '"details": {"resource": "network-object"}}'
    )

    mock_service = MagicMock()
    mock_service.delete_network_object.side_effect = api_error
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        delete_network_object.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert call_kwargs["msg"] == "Access denied"
    assert call_kwargs["error_code"] == "FORBIDDEN"
    assert call_kwargs["error_details"] == {"resource": "network-object"}
    assert call_kwargs["status_code"] == 403


@patch("plugins.modules.delete_network_object.Config")
@patch("plugins.modules.delete_network_object.NetworkObjectService")
@patch("plugins.modules.delete_network_object.AnsibleModule")
def test_should_pass_all_parameters_to_service(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    base_module_params_with_name: dict[str, Any],
) -> None:
    """run_module should pass all parameters correctly to the service."""
    mock_module_instance.params = base_module_params_with_name
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.delete_network_object.return_value = "resolved-uid-789"
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        delete_network_object.run_module()

    mock_service.delete_network_object.assert_called_once_with(
        uid=None,
        name="test-network-object",
    )


def test_build_argument_spec() -> None:
    """build_argument_spec should return proper spec with uid and name as optional."""
    spec = delete_network_object.build_argument_spec()

    assert "uid" in spec
    assert spec["uid"]["required"] is False
    assert spec["uid"]["type"] == "str"

    assert "name" in spec
    assert spec["name"]["required"] is False
    assert spec["name"]["type"] == "str"

    assert "profile" in spec
    assert spec["profile"]["default"] == "default"

    assert "config_path" in spec
    assert spec["config_path"]["required"] is False


@patch("plugins.modules.delete_network_object.Config")
@patch("plugins.modules.delete_network_object.NetworkObjectService")
@patch("plugins.modules.delete_network_object.AnsibleModule")
def test_check_mode_should_report_would_delete_when_object_exists(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module in check_mode should report changed without deleting when object exists."""
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    existing_obj = MagicMock()
    existing_obj.uid = "net-obj-uid-123"

    mock_service = MagicMock()
    mock_service.get_network_object.return_value = existing_obj
    mock_service.get_network_object_by_name.return_value = existing_obj
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        delete_network_object.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert "Would delete" in call_kwargs["msg"]
    assert call_kwargs["deleted_uid"] == "net-obj-uid-123"
    mock_service.delete_network_object.assert_not_called()


@patch("plugins.modules.delete_network_object.Config")
@patch("plugins.modules.delete_network_object.NetworkObjectService")
@patch("plugins.modules.delete_network_object.AnsibleModule")
def test_check_mode_should_report_no_change_when_object_not_found(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module in check_mode should report changed=False when object does not exist."""
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_object.return_value = None
    mock_service.get_network_object_by_name.return_value = None
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        delete_network_object.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert "not found" in call_kwargs["msg"]
    mock_service.delete_network_object.assert_not_called()


@patch("plugins.modules.delete_network_object.Config")
@patch("plugins.modules.delete_network_object.NetworkObjectService")
@patch("plugins.modules.delete_network_object.AnsibleModule")
def test_check_mode_should_fail_when_lookup_errors(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module in check_mode should fail on lookup/API errors."""
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_object.side_effect = Exception("API unavailable")
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        delete_network_object.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "Failed to check network object existence" in call_kwargs["msg"]
    assert "API unavailable" in call_kwargs["msg"]
    mock_service.delete_network_object.assert_not_called()

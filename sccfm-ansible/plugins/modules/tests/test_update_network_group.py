# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import update_network_group  # noqa: E402


def _make_current_group() -> MagicMock:
    """Creates a mock representing the current state of a network group."""
    obj = MagicMock()
    obj.uid = "net-grp-uid-456"
    obj.name = "test-network-group"
    obj.description = "Original description"
    obj.elements = []
    obj.labels = ["production"]
    obj.tags = {"environment": ["production"]}
    obj.object_type = "NETWORK_GROUP"
    obj.literals = ["10.0.1.100"]
    obj.referenced_object_uids = ["ref-uid-001"]
    obj.to_dict.return_value = {
        "uid": "net-grp-uid-456",
        "name": "test-network-group",
        "description": "Original description",
        "elements": [],
        "labels": ["production"],
        "tags": {"environment": ["production"]},
        "object_type": "NETWORK_GROUP",
        "literals": ["10.0.1.100"],
        "referenced_object_uids": ["ref-uid-001"],
    }
    return obj


def _make_updated_group() -> MagicMock:
    """Creates a mock representing the updated network group."""
    obj = MagicMock()
    obj.uid = "net-grp-uid-456"
    obj.name = "test-network-group"
    obj.description = "Updated description"
    obj.elements = []
    obj.labels = ["production", "web"]
    obj.tags = {"environment": ["production"]}
    obj.object_type = "NETWORK_GROUP"
    obj.literals = ["10.0.1.100"]
    obj.referenced_object_uids = ["ref-uid-001", "ref-uid-002"]
    obj.to_dict.return_value = {
        "uid": "net-grp-uid-456",
        "name": "test-network-group",
        "description": "Updated description",
        "elements": [],
        "labels": ["production", "web"],
        "tags": {"environment": ["production"]},
        "object_type": "NETWORK_GROUP",
        "literals": ["10.0.1.100"],
        "referenced_object_uids": ["ref-uid-001", "ref-uid-002"],
    }
    return obj


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    """Provides base module parameters for update."""
    return {
        "uid": None,
        "name": "test-network-group",
        "new_name": None,
        "referenced_objects": ["ref-uid-001", "ref-uid-002"],
        "description": None,
        "labels": None,
        "tags": None,
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


# ============================================================
# Successful update tests
# ============================================================


@patch("plugins.modules.update_network_group.Config")
@patch("plugins.modules.update_network_group.NetworkGroupService")
@patch("plugins.modules.update_network_group.AnsibleModule")
def test_should_update_when_referenced_objects_differ(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should update and return changed=True when referenced objects differ."""
    mock_ansible_module_class.return_value = mock_module_instance

    current = _make_current_group()
    updated = _make_updated_group()

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = current
    mock_service.update_network_group.return_value = updated
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_network_group.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert "Successfully updated" in call_kwargs["msg"]


@patch("plugins.modules.update_network_group.Config")
@patch("plugins.modules.update_network_group.NetworkGroupService")
@patch("plugins.modules.update_network_group.AnsibleModule")
def test_should_update_by_uid(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should look up group by UID and update it."""
    mock_module_instance.params["uid"] = "net-grp-uid-456"
    mock_module_instance.params["name"] = None
    mock_ansible_module_class.return_value = mock_module_instance

    current = _make_current_group()
    updated = _make_updated_group()

    list_response = MagicMock()
    list_response.items = [current]

    mock_service = MagicMock()
    mock_service.list_network_groups.return_value = list_response
    mock_service.update_network_group.return_value = updated
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_network_group.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    mock_service.update_network_group.assert_called_once()


@patch("plugins.modules.update_network_group.Config")
@patch("plugins.modules.update_network_group.NetworkGroupService")
@patch("plugins.modules.update_network_group.AnsibleModule")
def test_should_pass_all_parameters_to_service(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should pass all parameters correctly to the service."""
    mock_module_instance.params["new_name"] = "renamed-group"
    mock_module_instance.params["description"] = "New description"
    mock_module_instance.params["labels"] = ["staging"]
    mock_module_instance.params["tags"] = {"team": ["platform"]}
    mock_ansible_module_class.return_value = mock_module_instance

    current = _make_current_group()
    updated = _make_updated_group()

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = current
    mock_service.update_network_group.return_value = updated
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_network_group.run_module()

    mock_service.update_network_group.assert_called_once_with(
        uid="net-grp-uid-456",
        new_name="renamed-group",
        referenced_objects=["ref-uid-001", "ref-uid-002"],
        description="New description",
        labels=["staging"],
        tags={"team": ["platform"]},
    )


# ============================================================
# Idempotency tests
# ============================================================


@patch("plugins.modules.update_network_group.Config")
@patch("plugins.modules.update_network_group.NetworkGroupService")
@patch("plugins.modules.update_network_group.AnsibleModule")
def test_should_not_update_when_referenced_objects_match(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should return changed=False when referenced objects already match."""
    mock_module_instance.params["referenced_objects"] = ["ref-uid-001"]  # Same as current
    mock_ansible_module_class.return_value = mock_module_instance

    current = _make_current_group()

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = current
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_network_group.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert "already up to date" in call_kwargs["msg"]
    mock_service.update_network_group.assert_not_called()


@patch("plugins.modules.update_network_group.Config")
@patch("plugins.modules.update_network_group.NetworkGroupService")
@patch("plugins.modules.update_network_group.AnsibleModule")
def test_should_not_update_when_description_matches(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should return changed=False when description already matches."""
    mock_module_instance.params["referenced_objects"] = None
    mock_module_instance.params["description"] = "Original description"
    mock_ansible_module_class.return_value = mock_module_instance

    current = _make_current_group()

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = current
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_network_group.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    mock_service.update_network_group.assert_not_called()


@patch("plugins.modules.update_network_group.Config")
@patch("plugins.modules.update_network_group.NetworkGroupService")
@patch("plugins.modules.update_network_group.AnsibleModule")
def test_should_not_update_when_labels_match(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should return changed=False when labels already match."""
    mock_module_instance.params["referenced_objects"] = None
    mock_module_instance.params["labels"] = ["production"]
    mock_ansible_module_class.return_value = mock_module_instance

    current = _make_current_group()

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = current
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_network_group.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    mock_service.update_network_group.assert_not_called()


@patch("plugins.modules.update_network_group.Config")
@patch("plugins.modules.update_network_group.NetworkGroupService")
@patch("plugins.modules.update_network_group.AnsibleModule")
def test_should_not_update_when_name_matches(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should return changed=False when new_name equals current name."""
    mock_module_instance.params["referenced_objects"] = None
    mock_module_instance.params["new_name"] = "test-network-group"
    mock_ansible_module_class.return_value = mock_module_instance

    current = _make_current_group()

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = current
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_network_group.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    mock_service.update_network_group.assert_not_called()


# ============================================================
# Check mode tests
# ============================================================


@patch("plugins.modules.update_network_group.Config")
@patch("plugins.modules.update_network_group.NetworkGroupService")
@patch("plugins.modules.update_network_group.AnsibleModule")
def test_check_mode_should_report_change_without_modifying(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module in check_mode should report changed=True but not call update."""
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    current = _make_current_group()

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = current
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_network_group.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert "would be updated" in call_kwargs["msg"]
    mock_service.update_network_group.assert_not_called()


@patch("plugins.modules.update_network_group.Config")
@patch("plugins.modules.update_network_group.NetworkGroupService")
@patch("plugins.modules.update_network_group.AnsibleModule")
def test_check_mode_no_change_when_already_matching(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module in check_mode should report changed=False when already matching."""
    mock_module_instance.check_mode = True
    mock_module_instance.params["referenced_objects"] = ["ref-uid-001"]
    mock_ansible_module_class.return_value = mock_module_instance

    current = _make_current_group()

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = current
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_network_group.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False


# ============================================================
# Validation / error tests
# ============================================================


@patch("plugins.modules.update_network_group.Config")
@patch("plugins.modules.update_network_group.AnsibleModule")
def test_should_fail_when_no_update_fields_provided(
    mock_ansible_module_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail when no update fields are provided."""
    mock_module_instance.params["referenced_objects"] = None
    mock_ansible_module_class.return_value = mock_module_instance

    with pytest.raises(SystemExit):
        update_network_group.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "At least one update field" in call_kwargs["msg"]


@patch("plugins.modules.update_network_group.Config")
@patch("plugins.modules.update_network_group.NetworkGroupService")
@patch("plugins.modules.update_network_group.AnsibleModule")
def test_should_fail_when_group_not_found(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail when the target group is not found."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = None
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_network_group.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "not found" in call_kwargs["msg"]


@patch("plugins.modules.update_network_group.Config")
@patch("plugins.modules.update_network_group.NetworkGroupService")
@patch("plugins.modules.update_network_group.AnsibleModule")
def test_should_fail_on_service_exception(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail with error message when service raises."""
    mock_ansible_module_class.return_value = mock_module_instance

    current = _make_current_group()

    mock_service = MagicMock()
    mock_service.get_network_group_by_name.return_value = current
    mock_service.update_network_group.side_effect = Exception("API error: 400 Bad Request")
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        update_network_group.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "API error: 400 Bad Request" in call_kwargs["msg"]


@patch("plugins.modules.update_network_group.AnsibleModule")
def test_should_fail_if_region_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail when region is not provided."""
    del mock_module_instance.params["region"]
    mock_ansible_module_class.return_value = mock_module_instance

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            update_network_group.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "region is required" in call_kwargs["msg"]


@patch("plugins.modules.update_network_group.AnsibleModule")
def test_should_fail_if_api_token_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail when api_token is not provided."""
    del mock_module_instance.params["api_token"]
    mock_ansible_module_class.return_value = mock_module_instance

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            update_network_group.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "api_token is required" in call_kwargs["msg"]


# ============================================================
# _needs_update unit tests
# ============================================================


class TestNeedsUpdate:
    """Unit tests for the _needs_update helper function."""

    def test_returns_true_when_referenced_objects_differ(self) -> None:
        current = _make_current_group()
        assert (
            update_network_group._needs_update(
                current,
                new_name=None,
                referenced_objects=["ref-uid-001", "ref-uid-002"],
                description=None,
                labels=None,
                tags=None,
            )
            is True
        )

    def test_returns_true_when_new_name_differs(self) -> None:
        current = _make_current_group()
        assert (
            update_network_group._needs_update(
                current,
                new_name="renamed-group",
                referenced_objects=None,
                description=None,
                labels=None,
                tags=None,
            )
            is True
        )

    def test_returns_true_when_description_differs(self) -> None:
        current = _make_current_group()
        assert (
            update_network_group._needs_update(
                current,
                new_name=None,
                referenced_objects=None,
                description="New description",
                labels=None,
                tags=None,
            )
            is True
        )

    def test_returns_true_when_labels_differ(self) -> None:
        current = _make_current_group()
        assert (
            update_network_group._needs_update(
                current,
                new_name=None,
                referenced_objects=None,
                description=None,
                labels=["production", "new-label"],
                tags=None,
            )
            is True
        )

    def test_returns_true_when_tags_differ(self) -> None:
        current = _make_current_group()
        assert (
            update_network_group._needs_update(
                current,
                new_name=None,
                referenced_objects=None,
                description=None,
                labels=None,
                tags={"environment": ["staging"]},
            )
            is True
        )

    def test_returns_false_when_all_match(self) -> None:
        current = _make_current_group()
        assert (
            update_network_group._needs_update(
                current,
                new_name="test-network-group",
                referenced_objects=["ref-uid-001"],
                description="Original description",
                labels=["production"],
                tags={"environment": ["production"]},
            )
            is False
        )

    def test_returns_false_when_only_none_fields(self) -> None:
        current = _make_current_group()
        assert (
            update_network_group._needs_update(
                current,
                new_name=None,
                referenced_objects=None,
                description=None,
                labels=None,
                tags=None,
            )
            is False
        )

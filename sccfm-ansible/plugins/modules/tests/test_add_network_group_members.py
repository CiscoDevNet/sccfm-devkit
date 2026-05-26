# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import add_network_group_members  # noqa: E402


def _make_group(name: str = "test-network-group", refs: list[str] | None = None) -> MagicMock:
    obj = MagicMock()
    obj.uid = "net-grp-uid-456"
    obj.name = name
    obj.description = "Original description"
    obj.elements = []
    obj.labels = ["production"]
    obj.tags = {"environment": ["production"]}
    obj.object_type = "NETWORK_GROUP"
    obj.literals = ["10.0.1.100"]
    obj.referenced_object_uids = refs or ["ref-uid-001"]
    obj.to_dict.return_value = {
        "uid": obj.uid,
        "name": obj.name,
        "description": obj.description,
        "elements": obj.elements,
        "labels": obj.labels,
        "tags": obj.tags,
        "object_type": obj.object_type,
        "literals": obj.literals,
        "referenced_object_uids": obj.referenced_object_uids,
    }
    return obj


def _make_mutation_result(group: MagicMock, *, changed: bool) -> MagicMock:
    result = MagicMock()
    result.network_group = group
    result.changed = changed
    return result


@pytest.fixture
def mock_module_instance() -> MagicMock:
    mock_module = MagicMock()
    mock_module.params = {
        "uid": None,
        "name": "test-network-group",
        "referenced_objects": ["ref-uid-002"],
        "region": "us",
        "api_token": "test-token-123",
    }
    mock_module.check_mode = False
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


@patch("plugins.modules.add_network_group_members.Config")
@patch("plugins.modules.add_network_group_members.NetworkGroupService")
@patch("plugins.modules.add_network_group_members.AnsibleModule")
def test_should_add_members_when_change_is_needed(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    updated_group = _make_group(refs=["ref-uid-001", "ref-uid-002"])
    mutation_result = _make_mutation_result(updated_group, changed=True)

    mock_service = MagicMock()
    mock_service.add_network_group_members.return_value = mutation_result
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        add_network_group_members.run_module()

    mock_service.add_network_group_members.assert_called_once_with(
        uid=None,
        name="test-network-group",
        referenced_objects=["ref-uid-002"],
        apply_changes=True,
    )
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert "Successfully added members" in call_kwargs["msg"]


@patch("plugins.modules.add_network_group_members.Config")
@patch("plugins.modules.add_network_group_members.NetworkGroupService")
@patch("plugins.modules.add_network_group_members.AnsibleModule")
def test_should_return_changed_false_when_members_already_present(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    current_group = _make_group()
    mutation_result = _make_mutation_result(current_group, changed=False)

    mock_service = MagicMock()
    mock_service.add_network_group_members.return_value = mutation_result
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        add_network_group_members.run_module()

    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert "already contains all requested members" in call_kwargs["msg"]


@patch("plugins.modules.add_network_group_members.Config")
@patch("plugins.modules.add_network_group_members.NetworkGroupService")
@patch("plugins.modules.add_network_group_members.AnsibleModule")
def test_should_use_apply_changes_false_in_check_mode(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    current_group = _make_group()
    mutation_result = _make_mutation_result(current_group, changed=True)

    mock_service = MagicMock()
    mock_service.add_network_group_members.return_value = mutation_result
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        add_network_group_members.run_module()

    mock_service.add_network_group_members.assert_called_once_with(
        uid=None,
        name="test-network-group",
        referenced_objects=["ref-uid-002"],
        apply_changes=False,
    )
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert "would have members added" in call_kwargs["msg"]


@patch("plugins.modules.add_network_group_members.AnsibleModule")
def test_should_require_referenced_objects(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_module_instance.params["referenced_objects"] = []
    mock_ansible_module_class.return_value = mock_module_instance

    with pytest.raises(SystemExit):
        add_network_group_members.run_module()

    mock_module_instance.fail_json.assert_called_once()
    assert (
        "At least one referenced_objects entry"
        in mock_module_instance.fail_json.call_args[1]["msg"]
    )

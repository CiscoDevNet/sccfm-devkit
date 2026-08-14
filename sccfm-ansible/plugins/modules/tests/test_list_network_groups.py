# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import list_network_groups  # noqa: E402


@pytest.fixture
def sample_list_response() -> MagicMock:
    """Provides a sample NetworkGroupListResponse for testing."""
    response = MagicMock()
    response.count = 2
    response.limit = 50
    response.offset = 0

    obj1 = MagicMock()
    obj1.to_dict.return_value = {
        "uid": "uid-001",
        "name": "web-servers",
        "description": "Web server hosts",
        "elements": [],
        "labels": ["production"],
        "tags": {},
        "object_type": "NETWORK_GROUP",
        "literals": ["10.0.1.100", "10.0.1.101"],
        "referenced_object_uids": ["ref-uid-001"],
    }

    obj2 = MagicMock()
    obj2.to_dict.return_value = {
        "uid": "uid-002",
        "name": "app-subnets",
        "description": "Application subnets",
        "elements": [],
        "labels": ["staging"],
        "tags": {"env": ["staging"]},
        "object_type": "NETWORK_GROUP",
        "literals": ["10.0.2.0/24"],
        "referenced_object_uids": [],
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


@patch("plugins.modules.list_network_groups.Config")
@patch("plugins.modules.list_network_groups.NetworkGroupService")
@patch("plugins.modules.list_network_groups.AnsibleModule")
def test_should_list_network_groups_successfully(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_list_response: MagicMock,
) -> None:
    """run_module should list network groups and return changed=False."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.list_network_groups.return_value = sample_list_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        list_network_groups.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["count"] == 2
    assert len(call_kwargs["network_groups"]) == 2
    assert call_kwargs["network_groups"][0]["name"] == "web-servers"
    assert call_kwargs["network_groups"][1]["name"] == "app-subnets"


@patch("plugins.modules.list_network_groups.Config")
@patch("plugins.modules.list_network_groups.NetworkGroupService")
@patch("plugins.modules.list_network_groups.AnsibleModule")
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
        "profile": "default",
    }
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.list_network_groups.return_value = sample_list_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        list_network_groups.run_module()

    mock_service.list_network_groups.assert_called_once_with(
        limit=10,
        offset=20,
        query="name:web*",
    )


@patch("plugins.modules.list_network_groups.Config")
@patch("plugins.modules.list_network_groups.NetworkGroupService")
@patch("plugins.modules.list_network_groups.AnsibleModule")
def test_should_fail_if_service_raises_exception(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail with error message when service layer raises."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.list_network_groups.side_effect = Exception("API error: 500")
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        list_network_groups.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "API error: 500" in call_kwargs["msg"]


@patch("plugins.modules.list_network_groups.Config")
@patch("plugins.modules.list_network_groups.NetworkGroupService")
@patch("plugins.modules.list_network_groups.AnsibleModule")
def test_should_support_check_mode(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_list_response: MagicMock,
) -> None:
    """Read-only modules should return real results in check mode."""
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    mock_service = MagicMock()
    mock_service.list_network_groups.return_value = sample_list_response
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        list_network_groups.run_module()

    mock_module_instance.exit_json.assert_called_once()
    mock_service.list_network_groups.assert_called_once_with(limit=50, offset=0, query=None)
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert len(call_kwargs["network_groups"]) == 2
    assert call_kwargs["count"] == 2

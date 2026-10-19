# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch

from cisco_sccfm_core.errors import NotFoundError
from cisco_sccfm_core.services.object_management import NetworkObjectResponse, NetworkObjectService
from cisco_sccfm_core.services.policy.access_rule_service import (
    AccessRuleListResponse,
    AccessRuleResponse,
    AccessRuleService,
)
from cisco_sccfm_core.services.policy.policy_api_helper import PolicyApiHelper

SAMPLE_RULE_JSON: dict[str, Any] = {
    "uid": "rule-uid-123",
    "accessGroupUid": "ag-uid-456",
    "entityUid": "device-uid-789",
    "index": 1,
    "isActiveRule": True,
    "ruleAction": "PERMIT",
    "ruleType": "L3",
    "remark": "Allow web traffic",
    "sourceNetwork": {"name": "web-servers", "uid": "net-uid-1", "type": "NETWORK_OBJECT"},
    "destinationNetwork": {"name": "db-servers", "uid": "net-uid-2", "type": "NETWORK_OBJECT"},
    "protocol": {"name": "tcp"},
    "destinationPort": {"name": "443"},
    "sourcePort": None,
    "logSettings": {"level": "informational", "interval": 300},
    "ruleConfigurationText": "access-list outside_in extended permit tcp ...",
    "createdDate": "2026-01-01T00:00:00Z",
    "updatedDate": "2026-01-02T00:00:00Z",
}

SAMPLE_NET_OBJ = NetworkObjectResponse(
    uid="net-uid-1",
    name="web-servers",
    description="Web server pool",
    elements=[],
    labels=[],
    tags={},
    object_type="NETWORK_OBJECT",
    literal="10.0.1.0/24",
)

SAMPLE_NET_OBJ_2 = NetworkObjectResponse(
    uid="net-uid-2",
    name="db-servers",
    description="Database servers",
    elements=[],
    labels=[],
    tags={},
    object_type="NETWORK_OBJECT",
    literal="10.0.2.0/24",
)


def _mock_api_response(data: dict[str, Any], status: int = 200) -> Mock:
    response = Mock()
    response.status = status
    response.read.return_value = json.dumps(data).encode("utf-8")
    return response


def _build_service(monkeypatch: MonkeyPatch) -> tuple[AccessRuleService, Mock]:
    """Create a service with mocked API layer."""
    mock_rules_api = Mock()

    service = AccessRuleService.__new__(AccessRuleService)
    service._rules_api = mock_rules_api
    service._helper = PolicyApiHelper.__new__(PolicyApiHelper)
    service._network_object_service = NetworkObjectService.__new__(NetworkObjectService)

    return service, mock_rules_api


class TestAccessRuleServiceCreate:
    def test_create_calls_api_with_correct_params(self, monkeypatch: MonkeyPatch) -> None:
        service, mock_api = _build_service(monkeypatch)

        mock_api.create_access_rule_without_preload_content.return_value = _mock_api_response(
            SAMPLE_RULE_JSON, status=201
        )
        monkeypatch.setattr(
            NetworkObjectService,
            "get_network_object_by_name",
            lambda self, name: SAMPLE_NET_OBJ if name == "web-servers" else SAMPLE_NET_OBJ_2,
        )

        result = service.create_access_rule(
            access_group_uid="ag-uid-456",
            entity_uid="device-uid-789",
            index=1,
            rule_action="PERMIT",
            remark="Allow web traffic",
            source_network="web-servers",
            destination_network="db-servers",
            protocol="tcp",
            destination_port="443",
        )

        assert result.uid == "rule-uid-123"
        assert result.rule_action == "PERMIT"
        assert result.index == 1
        mock_api.create_access_rule_without_preload_content.assert_called_once()
        call_kwargs = mock_api.create_access_rule_without_preload_content.call_args
        create_input = call_kwargs.kwargs["access_rule_create_input"]
        assert create_input.access_group_uid == "ag-uid-456"
        assert create_input.entity_uid == "device-uid-789"
        assert create_input.source_network.name == "web-servers"
        assert create_input.destination_network.name == "db-servers"

    def test_create_without_network_objects(self, monkeypatch: MonkeyPatch) -> None:
        service, mock_api = _build_service(monkeypatch)
        mock_api.create_access_rule_without_preload_content.return_value = _mock_api_response(
            SAMPLE_RULE_JSON, status=201
        )

        result = service.create_access_rule(
            access_group_uid="ag-uid-456",
            entity_uid="device-uid-789",
            index=0,
            rule_action="DENY",
        )

        assert result.uid == "rule-uid-123"
        call_kwargs = mock_api.create_access_rule_without_preload_content.call_args
        create_input = call_kwargs.kwargs["access_rule_create_input"]
        assert create_input.source_network is None
        assert create_input.destination_network is None

    def test_create_raises_when_network_object_not_found(self, monkeypatch: MonkeyPatch) -> None:
        service, mock_api = _build_service(monkeypatch)
        monkeypatch.setattr(
            NetworkObjectService,
            "get_network_object_by_name",
            lambda self, name: None,
        )

        with pytest.raises(NotFoundError, match="Network object with name 'nonexistent' not found"):
            service.create_access_rule(
                access_group_uid="ag-uid-456",
                entity_uid="device-uid-789",
                index=0,
                source_network="nonexistent",
            )


class TestAccessRuleResponse:
    def test_from_dict_roundtrip(self) -> None:
        response = AccessRuleResponse.from_dict(SAMPLE_RULE_JSON)
        assert response.uid == "rule-uid-123"
        assert response.access_group_uid == "ag-uid-456"
        assert response.rule_action == "PERMIT"
        assert response.created_date == datetime(2026, 1, 1, tzinfo=UTC)
        assert response.source_network == {
            "name": "web-servers",
            "uid": "net-uid-1",
            "type": "NETWORK_OBJECT",
        }

        d = response.to_dict()
        assert d["uid"] == "rule-uid-123"
        assert d["rule_action"] == "PERMIT"
        assert d["created_date"] == "2026-01-01T00:00:00Z"

    def test_from_dict_preserves_missing_identifiers_as_none(self) -> None:
        response = AccessRuleResponse.from_dict({"index": 0})

        assert response.uid is None
        assert response.access_group_uid is None
        assert response.entity_uid is None


SAMPLE_LIST_JSON: dict[str, Any] = {
    "count": 2,
    "items": [SAMPLE_RULE_JSON, SAMPLE_RULE_JSON],
    "limit": 50,
    "offset": 0,
}


class TestAccessRuleServiceFetch:
    def test_fetch_returns_access_rule(self, monkeypatch: MonkeyPatch) -> None:
        service, mock_api = _build_service(monkeypatch)
        mock_api.fetch_access_rule_without_preload_content.return_value = _mock_api_response(
            SAMPLE_RULE_JSON
        )

        result = service.fetch_access_rule(uid="rule-uid-123")

        assert result.uid == "rule-uid-123"
        assert result.rule_action == "PERMIT"
        mock_api.fetch_access_rule_without_preload_content.assert_called_once_with(
            access_rule_uid="rule-uid-123"
        )


class TestAccessRuleServiceList:
    def test_list_returns_paginated_response(self, monkeypatch: MonkeyPatch) -> None:
        service, mock_api = _build_service(monkeypatch)
        mock_api.list_access_rules_without_preload_content.return_value = _mock_api_response(
            SAMPLE_LIST_JSON
        )

        result = service.list_access_rules(limit=50, offset=0)

        assert result.count == 2
        assert len(result.items) == 2
        assert result.items[0].uid == "rule-uid-123"
        mock_api.list_access_rules_without_preload_content.assert_called_once_with(
            limit="50", offset="0", q=None
        )

    def test_list_with_query(self, monkeypatch: MonkeyPatch) -> None:
        service, mock_api = _build_service(monkeypatch)
        empty_page: dict[str, Any] = {"count": 0, "items": [], "limit": 10, "offset": 0}
        mock_api.list_access_rules_without_preload_content.return_value = _mock_api_response(
            empty_page
        )

        result = service.list_access_rules(limit=10, offset=0, query="ruleAction:DENY")

        assert result.count == 0
        assert result.items == []
        mock_api.list_access_rules_without_preload_content.assert_called_once_with(
            limit="10", offset="0", q="ruleAction:DENY"
        )


class TestAccessRuleServiceModify:
    def test_modify_calls_api_with_correct_params(self, monkeypatch: MonkeyPatch) -> None:
        service, mock_api = _build_service(monkeypatch)
        mock_api.modify_access_rule_without_preload_content.return_value = _mock_api_response(
            SAMPLE_RULE_JSON
        )
        monkeypatch.setattr(
            NetworkObjectService,
            "get_network_object_by_name",
            lambda self, name: SAMPLE_NET_OBJ if name == "web-servers" else SAMPLE_NET_OBJ_2,
        )

        result = service.modify_access_rule(
            uid="rule-uid-123",
            remark="Updated remark",
            source_network="web-servers",
            destination_network="db-servers",
        )

        assert result.uid == "rule-uid-123"
        mock_api.modify_access_rule_without_preload_content.assert_called_once()
        call_kwargs = mock_api.modify_access_rule_without_preload_content.call_args
        assert call_kwargs.kwargs["access_rule_uid"] == "rule-uid-123"
        update_input = call_kwargs.kwargs["access_rule_update_input"]
        assert update_input.uid == "rule-uid-123"
        assert update_input.remark == "Updated remark"
        assert update_input.source_network.name == "web-servers"

    def test_modify_with_minimal_params(self, monkeypatch: MonkeyPatch) -> None:
        service, mock_api = _build_service(monkeypatch)
        mock_api.modify_access_rule_without_preload_content.return_value = _mock_api_response(
            SAMPLE_RULE_JSON
        )

        result = service.modify_access_rule(uid="rule-uid-123", rule_action="DENY")

        assert result.uid == "rule-uid-123"
        call_kwargs = mock_api.modify_access_rule_without_preload_content.call_args
        update_input = call_kwargs.kwargs["access_rule_update_input"]
        assert update_input.rule_action == "DENY"
        assert update_input.source_network is None
        assert update_input.destination_network is None


class TestAccessRuleServiceDelete:
    def test_delete_returns_uid(self, monkeypatch: MonkeyPatch) -> None:
        service, mock_api = _build_service(monkeypatch)
        delete_response = Mock()
        delete_response.status = 204
        delete_response.read.return_value = b""
        mock_api.delete_access_rule_without_preload_content.return_value = delete_response

        result = service.delete_access_rule(uid="rule-uid-123")

        assert result == "rule-uid-123"
        mock_api.delete_access_rule_without_preload_content.assert_called_once_with(
            access_rule_uid="rule-uid-123"
        )


class TestAccessRuleListResponse:
    def test_from_dict_roundtrip(self) -> None:
        response = AccessRuleListResponse.from_dict(SAMPLE_LIST_JSON)
        assert response.count == 2
        assert len(response.items) == 2
        assert response.items[0].uid == "rule-uid-123"
        assert response.limit == 50
        assert response.offset == 0

        d = response.to_dict()
        assert d["count"] == 2
        assert len(d["items"]) == 2
        assert d["items"][0]["uid"] == "rule-uid-123"

    def test_from_dict_empty(self) -> None:
        empty: dict[str, Any] = {"count": 0, "items": [], "limit": 50, "offset": 0}
        response = AccessRuleListResponse.from_dict(empty)
        assert response.count == 0
        assert response.items == []

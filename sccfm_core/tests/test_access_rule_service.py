from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch

from sccfm_core.errors import NotFoundError
from sccfm_core.services.object_management import NetworkObjectResponse, NetworkObjectService
from sccfm_core.services.policy.access_rule_service import (
    AccessRuleResponse,
    AccessRuleService,
)
from sccfm_core.services.policy.policy_api_helper import PolicyApiHelper

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

        with pytest.raises(NotFoundError, match="Network object 'nonexistent' not found"):
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
        assert response.source_network == {
            "name": "web-servers",
            "uid": "net-uid-1",
            "type": "NETWORK_OBJECT",
        }

        d = response.to_dict()
        assert d["uid"] == "rule-uid-123"
        assert d["rule_action"] == "PERMIT"

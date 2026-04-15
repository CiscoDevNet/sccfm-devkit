from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch

from sccfm_core.services.policy.access_group_service import (
    AccessGroupListResponse,
    AccessGroupResponse,
    AccessGroupService,
)
from sccfm_core.services.policy.policy_api_helper import PolicyApiHelper

SAMPLE_GROUP_JSON: dict[str, Any] = {
    "uid": "ag-uid-123",
    "name": "outside_access_in",
    "entityUid": "device-uid-456",
    "isShared": False,
    "sharedAccessGroupUid": None,
    "appliedTo": ["device-uid-456"],
    "resources": [{"interfaceName": "outside", "direction": "IN"}],
    "createdDate": "2026-01-01T00:00:00Z",
    "updatedDate": "2026-01-02T00:00:00Z",
}

SAMPLE_LIST_JSON: dict[str, Any] = {
    "count": 2,
    "items": [
        SAMPLE_GROUP_JSON,
        {
            "uid": "ag-uid-789",
            "name": "inside_access_out",
            "entityUid": "device-uid-456",
            "isShared": True,
            "sharedAccessGroupUid": "shared-uid-001",
            "appliedTo": None,
            "resources": None,
            "createdDate": "2026-02-01T00:00:00Z",
            "updatedDate": None,
        },
    ],
    "limit": 50,
    "offset": 0,
}


def _mock_api_response(data: dict[str, Any], status: int = 200) -> Mock:
    response = Mock()
    response.status = status
    response.read.return_value = json.dumps(data).encode("utf-8")
    return response


def _build_service() -> tuple[AccessGroupService, Mock]:
    mock_groups_api = Mock()
    service = AccessGroupService.__new__(AccessGroupService)
    service._groups_api = mock_groups_api
    service._helper = PolicyApiHelper.__new__(PolicyApiHelper)
    return service, mock_groups_api


class TestAccessGroupServiceFetch:
    def test_fetch_returns_access_group(self) -> None:
        service, mock_api = _build_service()
        mock_api.fetch_access_group_without_preload_content.return_value = _mock_api_response(
            SAMPLE_GROUP_JSON
        )

        result = service.fetch_access_group(uid="ag-uid-123")

        assert result.uid == "ag-uid-123"
        assert result.name == "outside_access_in"
        assert result.entity_uid == "device-uid-456"
        assert result.is_shared is False
        mock_api.fetch_access_group_without_preload_content.assert_called_once_with(
            access_group_uid="ag-uid-123"
        )


class TestAccessGroupServiceList:
    def test_list_returns_paginated_response(self) -> None:
        service, mock_api = _build_service()
        mock_api.list_access_groups_without_preload_content.return_value = _mock_api_response(
            SAMPLE_LIST_JSON
        )

        result = service.list_access_groups(limit=50, offset=0)

        assert result.count == 2
        assert len(result.items) == 2
        assert result.items[0].uid == "ag-uid-123"
        assert result.items[1].name == "inside_access_out"
        assert result.limit == 50
        assert result.offset == 0

    def test_list_with_query(self) -> None:
        service, mock_api = _build_service()
        mock_api.list_access_groups_without_preload_content.return_value = _mock_api_response(
            SAMPLE_LIST_JSON
        )

        service.list_access_groups(limit=10, offset=5, query="name:outside")

        mock_api.list_access_groups_without_preload_content.assert_called_once_with(
            limit="10",
            offset="5",
            q="name:outside",
        )


class TestAccessGroupResponse:
    def test_from_dict_roundtrip(self) -> None:
        response = AccessGroupResponse.from_dict(SAMPLE_GROUP_JSON)
        assert response.uid == "ag-uid-123"
        assert response.name == "outside_access_in"
        assert response.resources == [{"interfaceName": "outside", "direction": "IN"}]

        d = response.to_dict()
        assert d["uid"] == "ag-uid-123"
        assert d["name"] == "outside_access_in"


class TestAccessGroupListResponse:
    def test_from_dict_roundtrip(self) -> None:
        response = AccessGroupListResponse.from_dict(SAMPLE_LIST_JSON)
        assert response.count == 2
        assert len(response.items) == 2

        d = response.to_dict()
        assert d["count"] == 2
        assert len(d["items"]) == 2

    def test_from_dict_empty(self) -> None:
        response = AccessGroupListResponse.from_dict(
            {"count": 0, "items": [], "limit": 50, "offset": 0}
        )
        assert response.count == 0
        assert response.items == []

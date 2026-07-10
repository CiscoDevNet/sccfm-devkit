# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from scc_firewall_manager_sdk.exceptions import ApiException

from cisco_sccfm_core.services.object_management.network_object_service import (
    NetworkObjectListResponse,
    NetworkObjectResponse,
    NetworkObjectService,
)
from cisco_sccfm_core.services.object_management.object_api_helper import raise_for_status

SAMPLE_API_RESPONSE: dict[str, Any] = {
    "uid": "abc-123",
    "name": "my-network",
    "description": "Test network",
    "elements": ["10.10.0.0/24"],
    "labels": ["production"],
    "tags": {"env": ["prod"]},
    "value": {
        "objectType": "NETWORK_OBJECT",
        "defaultContent": {"literal": "10.10.0.0/24"},
        "overrides": [],
    },
}


class TestNetworkObjectResponseFromDict:
    """Tests for NetworkObjectResponse.from_dict parsing."""

    def test_parses_full_response(self) -> None:
        response = NetworkObjectResponse.from_dict(SAMPLE_API_RESPONSE)
        assert response.uid == "abc-123"
        assert response.name == "my-network"
        assert response.description == "Test network"
        assert response.elements == ["10.10.0.0/24"]
        assert response.labels == ["production"]
        assert response.tags == {"env": ["prod"]}
        assert response.object_type == "NETWORK_OBJECT"
        assert response.literal == "10.10.0.0/24"

    def test_handles_missing_value(self) -> None:
        data: dict[str, Any] = {"uid": "abc", "name": "net"}
        response = NetworkObjectResponse.from_dict(data)
        assert response.object_type == ""
        assert response.literal == ""

    def test_handles_missing_default_content(self) -> None:
        data: dict[str, Any] = {
            "uid": "abc",
            "name": "net",
            "value": {"objectType": "NETWORK_OBJECT"},
        }
        response = NetworkObjectResponse.from_dict(data)
        assert response.object_type == "NETWORK_OBJECT"
        assert response.literal == ""

    def test_defaults_empty_fields(self) -> None:
        response = NetworkObjectResponse.from_dict({})
        assert response.uid == ""
        assert response.name == ""
        assert response.description is None
        assert response.elements == []
        assert response.labels == []
        assert response.tags == {}
        assert response.object_type == ""
        assert response.literal == ""


class TestNetworkObjectResponseToDict:
    """Tests for NetworkObjectResponse.to_dict round-trip."""

    def test_to_dict_contains_all_fields(self) -> None:
        response = NetworkObjectResponse.from_dict(SAMPLE_API_RESPONSE)
        result = response.to_dict()
        assert result["uid"] == "abc-123"
        assert result["name"] == "my-network"
        assert result["object_type"] == "NETWORK_OBJECT"
        assert result["literal"] == "10.10.0.0/24"


class TestRaiseForStatus:
    """Tests for raise_for_status helper."""

    def test_2xx_does_not_raise(self) -> None:
        raise_for_status(200, "{}")
        raise_for_status(201, "{}")

    def test_4xx_raises_api_exception(self) -> None:
        body = '{"errorMsg":"Duplicate","errorCode":"CONFLICT","details":{}}'
        with pytest.raises(ApiException) as exc_info:
            raise_for_status(409, body)
        assert exc_info.value.status == 409
        assert exc_info.value.body == body

    def test_5xx_raises_api_exception(self) -> None:
        with pytest.raises(ApiException) as exc_info:
            raise_for_status(500, "error")
        assert exc_info.value.status == 500


SAMPLE_LIST_API_RESPONSE: dict[str, Any] = {
    "count": 2,
    "items": [
        SAMPLE_API_RESPONSE,
        {
            "uid": "def-456",
            "name": "other-network",
            "description": None,
            "elements": [],
            "labels": [],
            "tags": {},
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "192.168.1.0/24"},
            },
        },
    ],
    "limit": 50,
    "offset": 0,
}

SAMPLE_LIST_WITH_MIXED_TYPES: dict[str, Any] = {
    "count": 3,
    "items": [
        SAMPLE_API_RESPONSE,
        {
            "uid": "url-789",
            "name": "some-url-group",
            "description": None,
            "elements": [],
            "labels": [],
            "tags": {},
            "value": {
                "objectType": "URL_GROUP",
                "defaultContent": {"literal": "http://example.com"},
            },
        },
        {
            "uid": "grp-101",
            "name": "my-net-group",
            "description": None,
            "elements": [],
            "labels": [],
            "tags": {},
            "value": {
                "objectType": "NETWORK_GROUP",
                "defaultContent": {"literal": ""},
            },
        },
    ],
    "limit": 50,
    "offset": 0,
}


class TestNetworkObjectListResponseFromDict:
    """Tests for NetworkObjectListResponse.from_dict parsing."""

    def test_parses_full_response(self) -> None:
        response = NetworkObjectListResponse.from_dict(SAMPLE_LIST_API_RESPONSE)
        assert response.count == 2
        assert response.limit == 50
        assert response.offset == 0
        assert len(response.items) == 2
        assert response.items[0].uid == "abc-123"
        assert response.items[1].uid == "def-456"

    def test_handles_empty_items(self) -> None:
        data: dict[str, Any] = {"count": 0, "items": [], "limit": 50, "offset": 0}
        response = NetworkObjectListResponse.from_dict(data)
        assert response.count == 0
        assert response.items == []

    def test_handles_missing_items(self) -> None:
        data: dict[str, Any] = {"count": 0}
        response = NetworkObjectListResponse.from_dict(data)
        assert response.items == []
        assert response.limit == 0
        assert response.offset == 0

    def test_to_dict_round_trip(self) -> None:
        response = NetworkObjectListResponse.from_dict(SAMPLE_LIST_API_RESPONSE)
        result = response.to_dict()
        assert result["count"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["uid"] == "abc-123"
        assert result["limit"] == 50
        assert result["offset"] == 0

    def test_parses_mixed_types_without_filtering(self) -> None:
        """from_dict itself does not filter — it preserves all items."""
        response = NetworkObjectListResponse.from_dict(SAMPLE_LIST_WITH_MIXED_TYPES)
        assert response.count == 3
        assert len(response.items) == 3
        types = {item.object_type for item in response.items}
        assert "URL_GROUP" in types


class TestNetworkObjectTypeValidation:
    """Tests for type-safety checks in NetworkObjectService."""

    def test_get_network_object_returns_none_for_wrong_type(self) -> None:
        """get_network_object returns None when the UID resolves to a different objectType."""
        service = NetworkObjectService.__new__(NetworkObjectService)
        mock_response = MagicMock()
        mock_response.status = 200
        service._object_api = MagicMock()
        service._object_api.get_object_without_preload_content.return_value = mock_response
        service._helper = MagicMock()
        service._helper.read_raw_response.return_value = {
            "uid": "abc-123",
            "name": "some-group",
            "value": {
                "objectType": "NETWORK_GROUP",
                "defaultContent": {"literals": []},
            },
        }

        result = service.get_network_object("abc-123")

        assert result is None

    def test_get_network_object_by_name_uses_type_filter(self) -> None:
        """get_network_object_by_name includes objectType:NETWORK_OBJECT in its query."""
        service = NetworkObjectService.__new__(NetworkObjectService)
        service._object_api = MagicMock()
        service._helper = MagicMock()
        service._helper.read_raw_response.return_value = {"items": []}

        service.get_network_object_by_name("test-obj")

        call_kwargs = service._object_api.get_objects_without_preload_content.call_args.kwargs
        assert "objectType:NETWORK_OBJECT" in call_kwargs["q"]


class TestBuildFilteredQuery:
    """Tests for build_filtered_query utility."""

    def test_appends_filter_to_user_query(self) -> None:
        from cisco_sccfm_core.services.object_management.utils import build_filtered_query

        result = build_filtered_query("name:*network-obj*", "objectType:NETWORK_OBJECT")
        assert result == "name:*network-obj* AND objectType:NETWORK_OBJECT"

    def test_returns_filter_when_query_is_none(self) -> None:
        from cisco_sccfm_core.services.object_management.utils import build_filtered_query

        result = build_filtered_query(None, "objectType:NETWORK_OBJECT")
        assert result == "objectType:NETWORK_OBJECT"

    def test_returns_filter_when_query_is_empty(self) -> None:
        from cisco_sccfm_core.services.object_management.utils import build_filtered_query

        result = build_filtered_query("", "objectType:NETWORK_OBJECT")
        assert result == "objectType:NETWORK_OBJECT"

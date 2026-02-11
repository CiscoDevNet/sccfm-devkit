from __future__ import annotations

from typing import Any

import pytest
from scc_firewall_manager_sdk.exceptions import ApiException

from sccfm_core.services.object_management.network_object_service import (
    NetworkObjectResponse,
    NetworkObjectService,
)

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
    """Tests for NetworkObjectService._raise_for_status."""

    def test_2xx_does_not_raise(self) -> None:
        NetworkObjectService._raise_for_status(200, "{}")
        NetworkObjectService._raise_for_status(201, "{}")

    def test_4xx_raises_api_exception(self) -> None:
        body = '{"errorMsg":"Duplicate","errorCode":"CONFLICT","details":{}}'
        with pytest.raises(ApiException) as exc_info:
            NetworkObjectService._raise_for_status(409, body)
        assert exc_info.value.status == 409
        assert exc_info.value.body == body

    def test_5xx_raises_api_exception(self) -> None:
        with pytest.raises(ApiException) as exc_info:
            NetworkObjectService._raise_for_status(500, "error")
        assert exc_info.value.status == 500

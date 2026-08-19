# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for NetworkGroupResponse parsing and serialization."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from cisco_sccfm_core.errors import NotFoundError
from cisco_sccfm_core.services.object_management.network_group_service import (
    NetworkGroupResponse,
    NetworkGroupService,
)
from cisco_sccfm_core.services.object_management.network_object_service import (
    NetworkObjectResponse,
    NetworkObjectService,
)

SAMPLE_API_RESPONSE: dict[str, Any] = {
    "uid": "grp-abc-123",
    "name": "my-network-group",
    "description": "A test network group",
    "elements": ["10.0.0.0/8"],
    "labels": ["production"],
    "tags": {"env": ["prod"]},
    "value": {
        "objectType": "NETWORK_GROUP",
        "defaultContent": {
            "literals": [
                {"literal": "10.10.0.0/24"},
                {"literal": "192.168.1.0/24"},
            ],
            "referencedObjectUids": ["uid-member-1", "uid-member-2"],
        },
    },
}


class TestNetworkGroupResponseFromDict:
    """Tests for NetworkGroupResponse.from_dict."""

    def test_parses_full_response(self) -> None:
        result = NetworkGroupResponse.from_dict(SAMPLE_API_RESPONSE)

        assert result.uid == "grp-abc-123"
        assert result.name == "my-network-group"
        assert result.description == "A test network group"
        assert result.object_type == "NETWORK_GROUP"
        assert result.literals == ["10.10.0.0/24", "192.168.1.0/24"]
        assert result.referenced_object_uids == ["uid-member-1", "uid-member-2"]
        assert result.labels == ["production"]
        assert result.tags == {"env": ["prod"]}

    def test_handles_missing_value(self) -> None:
        data: dict[str, Any] = {"uid": "grp-1", "name": "empty"}
        result = NetworkGroupResponse.from_dict(data)

        assert result.uid == "grp-1"
        assert result.object_type == ""
        assert result.literals == []
        assert result.referenced_object_uids == []

    def test_handles_missing_default_content(self) -> None:
        data: dict[str, Any] = {
            "uid": "grp-2",
            "name": "no-content",
            "value": {"objectType": "NETWORK_GROUP"},
        }
        result = NetworkGroupResponse.from_dict(data)

        assert result.object_type == "NETWORK_GROUP"
        assert result.literals == []
        assert result.referenced_object_uids == []

    def test_handles_empty_literals_and_refs(self) -> None:
        data: dict[str, Any] = {
            "uid": "grp-3",
            "name": "empty-group",
            "value": {
                "objectType": "NETWORK_GROUP",
                "defaultContent": {
                    "literals": [],
                    "referencedObjectUids": [],
                },
            },
        }
        result = NetworkGroupResponse.from_dict(data)

        assert result.literals == []
        assert result.referenced_object_uids == []

    def test_defaults_empty_fields(self) -> None:
        result = NetworkGroupResponse.from_dict({})

        assert result.uid == ""
        assert result.name == ""
        assert result.description is None
        assert result.elements == []
        assert result.labels == []
        assert result.tags == {}
        assert result.object_type == ""
        assert result.literals == []
        assert result.referenced_object_uids == []

    def test_skips_literals_without_recognised_key(self) -> None:
        """Literals missing both 'literal' and 'url' keys should be excluded."""
        data: dict[str, Any] = {
            "uid": "grp-4",
            "name": "partial",
            "value": {
                "objectType": "NETWORK_GROUP",
                "defaultContent": {
                    "literals": [
                        {"literal": "10.0.0.0/8"},
                        {},
                        {"literal": ""},
                        {"literal": "192.168.0.0/16"},
                    ],
                },
            },
        }
        result = NetworkGroupResponse.from_dict(data)

        assert result.literals == ["10.0.0.0/8", "192.168.0.0/16"]

    def test_parses_url_literals(self) -> None:
        """URL content items should be extracted via the 'url' key."""
        data: dict[str, Any] = {
            "uid": "grp-5",
            "name": "url-group",
            "value": {
                "objectType": "NETWORK_GROUP",
                "defaultContent": {
                    "literals": [
                        {"url": "https://example.com"},
                        {"url": "https://acme.dev"},
                    ],
                },
            },
        }
        result = NetworkGroupResponse.from_dict(data)

        assert result.literals == ["https://example.com", "https://acme.dev"]

    def test_parses_mixed_network_and_url_literals(self) -> None:
        """Both network and URL literal types should be extracted."""
        data: dict[str, Any] = {
            "uid": "grp-6",
            "name": "mixed-group",
            "value": {
                "objectType": "NETWORK_GROUP",
                "defaultContent": {
                    "literals": [
                        {"literal": "10.0.0.0/8"},
                        {"url": "https://example.com"},
                    ],
                },
            },
        }
        result = NetworkGroupResponse.from_dict(data)

        assert result.literals == ["10.0.0.0/8", "https://example.com"]


class TestNetworkGroupResponseToDict:
    """Tests for NetworkGroupResponse.to_dict."""

    def test_to_dict_contains_all_fields(self) -> None:
        response = NetworkGroupResponse(
            uid="grp-abc",
            name="test-group",
            description="desc",
            elements=["10.0.0.0/8"],
            labels=["l1"],
            tags={"k": ["v"]},
            object_type="NETWORK_GROUP",
            literals=["10.0.0.0/8"],
            referenced_object_uids=["uid-1"],
        )
        d = response.to_dict()

        assert d["uid"] == "grp-abc"
        assert d["name"] == "test-group"
        assert d["description"] == "desc"
        assert d["object_type"] == "NETWORK_GROUP"
        assert d["literals"] == ["10.0.0.0/8"]
        assert d["referenced_object_uids"] == ["uid-1"]
        assert d["labels"] == ["l1"]
        assert d["tags"] == {"k": ["v"]}

    def test_to_dict_round_trip(self) -> None:
        original = NetworkGroupResponse.from_dict(SAMPLE_API_RESPONSE)
        d = original.to_dict()

        assert d["uid"] == "grp-abc-123"
        assert d["literals"] == ["10.10.0.0/24", "192.168.1.0/24"]
        assert d["referenced_object_uids"] == ["uid-member-1", "uid-member-2"]


class TestNetworkGroupServiceCreateValidation:
    """Tests for create_network_group input validation."""

    @staticmethod
    def _stub_init(self: NetworkGroupService, config: Any) -> None:
        return None

    def test_should_reject_empty_group(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Service should raise ValueError when no content is provided."""
        monkeypatch.setattr(NetworkGroupService, "__init__", self._stub_init)
        service = NetworkGroupService.__new__(NetworkGroupService)
        self._stub_init(service, None)

        with pytest.raises(ValueError, match="At least one literal or referenced object"):
            service.create_network_group(name="empty-group")

    def test_should_reject_explicit_empty_lists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Service should raise ValueError for explicitly empty literals and referenced objects."""
        monkeypatch.setattr(NetworkGroupService, "__init__", self._stub_init)
        service = NetworkGroupService.__new__(NetworkGroupService)
        self._stub_init(service, None)

        with pytest.raises(ValueError, match="At least one literal or referenced object"):
            service.create_network_group(
                name="empty-group", network_literals=[], referenced_objects=[]
            )

    def test_should_reject_blank_literal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Service should raise ValueError when a literal value is empty or blank."""
        monkeypatch.setattr(NetworkGroupService, "__init__", self._stub_init)
        service = NetworkGroupService.__new__(NetworkGroupService)
        self._stub_init(service, None)

        with pytest.raises(ValueError, match="Literal values must not be empty"):
            service.create_network_group(
                name="bad-literals",
                network_literals=["10.0.0.0/8", "", "192.168.0.0/16"],
            )

    def test_should_reject_whitespace_only_literal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Service should raise ValueError when a literal is whitespace-only."""
        monkeypatch.setattr(NetworkGroupService, "__init__", self._stub_init)
        service = NetworkGroupService.__new__(NetworkGroupService)
        self._stub_init(service, None)

        with pytest.raises(ValueError, match="Literal values must not be empty"):
            service.create_network_group(name="ws-literals", network_literals=["  "])

    def test_should_reject_blank_referenced_object_uid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Service should raise ValueError when a referenced object UID is empty or blank."""
        monkeypatch.setattr(NetworkGroupService, "__init__", self._stub_init)
        service = NetworkGroupService.__new__(NetworkGroupService)
        self._stub_init(service, None)

        with pytest.raises(ValueError, match="Referenced object UIDs must not be empty"):
            service.create_network_group(name="bad-refs", referenced_objects=["uid-1", ""])

    def test_should_reject_mixed_literal_types(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Service should raise ValueError when both literal types are given."""
        monkeypatch.setattr(NetworkGroupService, "__init__", self._stub_init)
        service = NetworkGroupService.__new__(NetworkGroupService)
        self._stub_init(service, None)

        with pytest.raises(ValueError, match="Only one literal type"):
            service.create_network_group(
                name="mixed",
                network_literals=["10.0.0.0/8"],
                url_literals=["https://example.com"],
            )


class TestReferencedObjectNameResolution:
    """Tests for _resolve_referenced_object_uids and _is_uuid."""

    VALID_UUID = "12345678-1234-5678-1234-567812345678"

    def test_is_uuid_with_valid_uuid(self) -> None:
        assert NetworkGroupService._is_uuid(self.VALID_UUID) is True

    def test_is_uuid_with_name(self) -> None:
        assert NetworkGroupService._is_uuid("my-network-object") is False

    def test_is_uuid_with_empty_string(self) -> None:
        assert NetworkGroupService._is_uuid("") is False

    def test_resolve_passes_uuids_through(self) -> None:
        """UIDs should be validated via get_network_object and resolved to the returned UID."""
        service = NetworkGroupService.__new__(NetworkGroupService)
        mock_obj = MagicMock(spec=NetworkObjectResponse)
        mock_obj.uid = self.VALID_UUID
        service._network_object_service = MagicMock(spec=NetworkObjectService)
        service._network_object_service.get_network_object.return_value = mock_obj

        result = service._resolve_referenced_object_uids([self.VALID_UUID])

        assert result == [self.VALID_UUID]
        service._network_object_service.get_network_object.assert_called_once_with(
            uid=self.VALID_UUID
        )
        service._network_object_service.get_network_object_by_name.assert_not_called()

    def test_resolve_looks_up_names(self) -> None:
        """Non-UUID referenced objects should be resolved by name via the network object service."""
        service = NetworkGroupService.__new__(NetworkGroupService)
        mock_obj = MagicMock(spec=NetworkObjectResponse)
        mock_obj.uid = "resolved-uid-abc"
        service._network_object_service = MagicMock(spec=NetworkObjectService)
        service._network_object_service.get_network_object_by_name.return_value = mock_obj

        result = service._resolve_referenced_object_uids(["my-object"])

        assert result == ["resolved-uid-abc"]
        service._network_object_service.get_network_object_by_name.assert_called_once_with(
            name="my-object"
        )

    def test_resolve_mixed_uids_and_names(self) -> None:
        """Should handle a mix of UIDs and names in a single call."""
        service = NetworkGroupService.__new__(NetworkGroupService)
        uid_obj = MagicMock(spec=NetworkObjectResponse)
        uid_obj.uid = self.VALID_UUID
        name_obj = MagicMock(spec=NetworkObjectResponse)
        name_obj.uid = "resolved-uid-xyz"
        service._network_object_service = MagicMock(spec=NetworkObjectService)
        service._network_object_service.get_network_object.return_value = uid_obj
        service._network_object_service.get_network_object_by_name.return_value = name_obj

        result = service._resolve_referenced_object_uids([self.VALID_UUID, "my-object"])

        assert result == [self.VALID_UUID, "resolved-uid-xyz"]

    def test_resolve_raises_not_found_for_unknown_name(self) -> None:
        """Should raise NotFoundError when a name cannot be resolved."""
        service = NetworkGroupService.__new__(NetworkGroupService)
        service._network_object_service = MagicMock(spec=NetworkObjectService)
        service._network_object_service.get_network_object_by_name.return_value = None

        with pytest.raises(NotFoundError, match="Network object with name 'missing' not found"):
            service._resolve_referenced_object_uids(["missing"])


class TestNetworkGroupTypeValidation:
    """Tests for type-safety checks in NetworkGroupService."""

    def test_get_network_group_returns_none_for_wrong_type(self) -> None:
        """get_network_group returns None when the UID resolves to a different objectType."""
        service = NetworkGroupService.__new__(NetworkGroupService)
        mock_response = MagicMock()
        mock_response.status = 200
        service._object_api = MagicMock()
        service._object_api.get_object_without_preload_content.return_value = mock_response
        service._helper = MagicMock()
        service._helper.read_raw_response.return_value = {
            "uid": "obj-123",
            "name": "some-network-object",
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "10.0.0.0/8"},
            },
        }

        result = service.get_network_group(uid="obj-123")

        assert result is None

    def test_resolve_referenced_object_uids_validates_uuid_existence(self) -> None:
        """Raises NotFoundError for a valid UUID that doesn't exist as a network object."""
        service = NetworkGroupService.__new__(NetworkGroupService)
        service._network_object_service = MagicMock(spec=NetworkObjectService)
        service._network_object_service.get_network_object.return_value = None

        valid_uuid = "12345678-1234-5678-1234-567812345678"

        with pytest.raises(
            NotFoundError, match=f"Network object with UID '{valid_uuid}' not found"
        ):
            service._resolve_referenced_object_uids([valid_uuid])

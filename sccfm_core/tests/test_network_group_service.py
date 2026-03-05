from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch

from sccfm_core.errors import NotFoundError
from sccfm_core.services.object_management import (
    NetworkGroupService,
    NetworkObjectResponse,
    NetworkObjectService,
)
from sccfm_core.services.object_management.network_group_service import (
    NetworkGroupResponse as GroupResponse,
)
from sccfm_core.services.object_management.object_api_helper import ObjectApiHelper

SAMPLE_GROUP = NetworkObjectResponse(
    uid="grp-123",
    name="test-network-group",
    description="Test group",
    elements=["10.0.0.0/24"],
    labels=["test"],
    tags={"env": ["test"]},
    object_type="NETWORK_GROUP",
    literal="",
)


class TestNetworkGroupServiceDelete:
    """Tests for NetworkGroupService.delete_network_group method."""

    def test_delete_by_uid_calls_api(self, monkeypatch: MonkeyPatch) -> None:
        """Service should call API with correct uid parameter."""
        mock_api = Mock()

        raw_api_response = {
            "uid": "grp-123",
            "name": "test-network-group",
            "description": "Test group",
            "elements": ["10.0.0.0/24"],
            "labels": ["test"],
            "tags": {"env": ["test"]},
            "value": {
                "objectType": "NETWORK_GROUP",
                "defaultContent": {},
            },
        }
        get_response = Mock()
        get_response.status = 200
        get_response.read.return_value = json.dumps(raw_api_response).encode("utf-8")
        mock_api.get_object_without_preload_content.return_value = get_response

        delete_response = Mock()
        delete_response.read.return_value = b""
        delete_response.status = 200
        mock_api.delete_object_without_preload_content.return_value = delete_response

        service = NetworkGroupService.__new__(NetworkGroupService)
        service._object_api = mock_api
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)

        result = service.delete_network_group(uid="test-uid")

        assert result == "test-uid"
        mock_api.get_object_without_preload_content.assert_called_once_with(uid="test-uid")
        mock_api.delete_object_without_preload_content.assert_called_once_with(uid="test-uid")

    def test_delete_by_name_resolves_to_uid(self, monkeypatch: MonkeyPatch) -> None:
        """Service should resolve name to uid before deleting."""
        mock_api = Mock()
        mock_helper = Mock()
        mock_response = Mock()
        mock_response.read.return_value = b""
        mock_response.status = 200
        mock_api.delete_object_without_preload_content.return_value = mock_response

        def fake_get_by_name(self: NetworkGroupService, name: str) -> NetworkObjectResponse:
            return SAMPLE_GROUP

        service = NetworkGroupService.__new__(NetworkGroupService)
        service._object_api = mock_api
        service._helper = mock_helper
        monkeypatch.setattr(NetworkGroupService, "get_network_group_by_name", fake_get_by_name)

        result = service.delete_network_group(name="test-network-group")

        assert result == "grp-123"
        mock_api.delete_object_without_preload_content.assert_called_once_with(uid="grp-123")

    def test_delete_raises_error_when_name_not_found(self, monkeypatch: MonkeyPatch) -> None:
        """Service should raise NotFoundError when name doesn't exist."""

        def fake_get_by_name(self: NetworkGroupService, name: str) -> None:
            return None

        service = NetworkGroupService.__new__(NetworkGroupService)
        service._object_api = Mock()
        service._helper = Mock()
        monkeypatch.setattr(NetworkGroupService, "get_network_group_by_name", fake_get_by_name)

        with pytest.raises(NotFoundError, match="not found"):
            service.delete_network_group(name="missing")

    def test_delete_validates_parameters(self) -> None:
        """Service should validate that exactly one parameter is provided."""
        service = NetworkGroupService.__new__(NetworkGroupService)

        with pytest.raises(ValueError, match="must be provided"):
            service.delete_network_group()

        with pytest.raises(ValueError, match="Only one"):
            service.delete_network_group(uid="uid-123", name="name-123")


def _make_raw_api_response(
    *,
    uid: str = "00000000-0000-0000-0000-000000000001",
    name: str = "test-group",
    network_literals: list[str] | None = None,
    url_literals: list[str] | None = None,
    referenced_object_uids: list[str] | None = None,
) -> dict[str, object]:
    """Build a raw API response dict for a network group."""
    literals = []
    for lit in network_literals or []:
        literals.append({"literal": lit})
    for url in url_literals or []:
        literals.append({"url": url})
    return {
        "uid": uid,
        "name": name,
        "description": "Test group",
        "elements": [],
        "labels": ["test"],
        "tags": {"env": ["test"]},
        "value": {
            "objectType": "NETWORK_GROUP",
            "defaultContent": {
                "literals": literals or None,
                "referencedObjectUids": referenced_object_uids,
            },
        },
    }


def _mock_api_response(data: dict[str, object]) -> Mock:
    """Create a mock HTTP response returning given data."""
    resp = Mock()
    resp.status = 200
    resp.read.return_value = json.dumps(data).encode("utf-8")
    return resp


def _mock_network_object_service_for_uid(uid: str) -> Mock:
    """Build a mock NetworkObjectService that resolves a single UID."""
    mock_obj_service = Mock(spec=NetworkObjectService)
    mock_obj_service.get_network_object.return_value = NetworkObjectResponse(
        uid=uid,
        name="ref-obj",
        description=None,
        elements=[],
        labels=[],
        tags={},
        object_type="NETWORK_OBJECT",
        literal="10.0.0.1",
    )
    return mock_obj_service


class TestNetworkGroupServiceUpdate:
    """Tests for NetworkGroupService.update_network_group method."""

    def test_update_preserves_existing_literals(self, monkeypatch: MonkeyPatch) -> None:
        """Updating referenced objects should preserve existing network literals."""
        old_ref = "00000000-0000-0000-0000-000000000010"
        new_ref = "00000000-0000-0000-0000-000000000020"
        existing = _make_raw_api_response(
            network_literals=["10.0.0.0/24", "192.168.1.0/24"],
            referenced_object_uids=[old_ref],
        )
        updated = _make_raw_api_response(
            network_literals=["10.0.0.0/24", "192.168.1.0/24"],
            referenced_object_uids=[new_ref],
        )

        mock_api = Mock()
        mock_api.get_object_without_preload_content.return_value = _mock_api_response(existing)
        mock_api.modify_object_without_preload_content.return_value = _mock_api_response(updated)

        service = NetworkGroupService.__new__(NetworkGroupService)
        service._object_api = mock_api
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._network_object_service = _mock_network_object_service_for_uid(new_ref)

        result = service.update_network_group(
            uid="00000000-0000-0000-0000-000000000001",
            referenced_objects=[new_ref],
        )

        assert result.referenced_object_uids == [new_ref]
        assert result.literals == ["10.0.0.0/24", "192.168.1.0/24"]

        call_kwargs = mock_api.modify_object_without_preload_content.call_args
        update_req = call_kwargs.kwargs["update_request"]
        content = update_req.value.default_content.actual_instance
        assert content.referenced_object_uids == [new_ref]
        assert len(content.literals) == 2

    def test_update_preserves_existing_url_literals(self, monkeypatch: MonkeyPatch) -> None:
        """Updating referenced objects should preserve existing URL literals."""
        old_ref = "00000000-0000-0000-0000-000000000010"
        new_ref = "00000000-0000-0000-0000-000000000020"
        existing = _make_raw_api_response(
            url_literals=["https://example.com"],
            referenced_object_uids=[old_ref],
        )
        updated = _make_raw_api_response(
            url_literals=["https://example.com"],
            referenced_object_uids=[new_ref],
        )

        mock_api = Mock()
        mock_api.get_object_without_preload_content.return_value = _mock_api_response(existing)
        mock_api.modify_object_without_preload_content.return_value = _mock_api_response(updated)

        service = NetworkGroupService.__new__(NetworkGroupService)
        service._object_api = mock_api
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._network_object_service = _mock_network_object_service_for_uid(new_ref)

        result = service.update_network_group(
            uid="00000000-0000-0000-0000-000000000001",
            referenced_objects=[new_ref],
        )

        call_kwargs = mock_api.modify_object_without_preload_content.call_args
        update_req = call_kwargs.kwargs["update_request"]
        content = update_req.value.default_content.actual_instance
        assert len(content.literals) == 1
        assert content.referenced_object_uids == [new_ref]

    def test_update_without_referenced_objects_skips_content_fetch(self) -> None:
        """Non-content updates should not fetch or rebuild content."""
        existing = _make_raw_api_response()

        mock_api = Mock()
        mock_api.get_object_without_preload_content.return_value = _mock_api_response(existing)
        mock_api.modify_object_without_preload_content.return_value = _mock_api_response(existing)

        service = NetworkGroupService.__new__(NetworkGroupService)
        service._object_api = mock_api
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)

        service.update_network_group(
            uid="00000000-0000-0000-0000-000000000001",
            description="new desc",
        )

        call_kwargs = mock_api.modify_object_without_preload_content.call_args
        update_req = call_kwargs.kwargs["update_request"]
        assert update_req.value is None
        assert update_req.description == "new desc"
        # Only one GET call for _resolve_uid, no second for content
        assert mock_api.get_object_without_preload_content.call_count == 1

    def test_update_validates_parameters(self) -> None:
        """Service should validate that exactly one identifier is provided."""
        service = NetworkGroupService.__new__(NetworkGroupService)

        with pytest.raises(ValueError, match="must be provided"):
            service.update_network_group(description="test")

        with pytest.raises(ValueError, match="Only one"):
            service.update_network_group(uid="uid", name="name", description="test")

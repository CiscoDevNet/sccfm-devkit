from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch

from sccfm_core.errors import NotFoundError
from sccfm_core.services.object_management import NetworkGroupService, NetworkObjectResponse

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

        get_response = Mock()
        get_response.status = 200
        get_response.read.return_value = json.dumps(SAMPLE_GROUP.to_dict()).encode("utf-8")
        mock_api.get_object_without_preload_content.return_value = get_response

        delete_response = Mock()
        delete_response.read.return_value = b""
        delete_response.status = 200
        mock_api.delete_object_without_preload_content.return_value = delete_response

        service = NetworkGroupService.__new__(NetworkGroupService)
        service._object_api = mock_api

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
        monkeypatch.setattr(NetworkGroupService, "_get_network_group_by_name", fake_get_by_name)

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
        monkeypatch.setattr(NetworkGroupService, "_get_network_group_by_name", fake_get_by_name)

        with pytest.raises(NotFoundError, match="not found"):
            service.delete_network_group(name="missing")

    def test_delete_validates_parameters(self) -> None:
        """Service should validate that exactly one parameter is provided."""
        service = NetworkGroupService.__new__(NetworkGroupService)

        with pytest.raises(ValueError, match="must be provided"):
            service.delete_network_group()

        with pytest.raises(ValueError, match="Only one"):
            service.delete_network_group(uid="uid-123", name="name-123")

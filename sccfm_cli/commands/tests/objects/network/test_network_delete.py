from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk.exceptions import ApiException

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.errors import NotFoundError
from sccfm_core.services import NetworkObjectService
from sccfm_core.services.object_management import NetworkObjectResponse

SAMPLE_OBJECT = NetworkObjectResponse(
    uid="obj-123",
    name="test-network",
    description="Test object",
    elements=["10.0.0.0/24"],
    labels=["test"],
    tags={"env": ["test"]},
    object_type="NETWORK_OBJECT",
    literal="10.0.0.0/24",
)


def _stub_init(self: NetworkObjectService, config: Any) -> None:
    return None


class TestNetworkDeleteByUID:
    """Tests for deleting network objects by UID."""

    def test_should_delete_by_uid(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Delete command should successfully delete object by UID."""
        captured: dict[str, Any] = {}

        def fake_delete(
            self: NetworkObjectService,
            uid: str | None = None,
            name: str | None = None,
        ) -> str:
            captured["uid"] = uid
            captured["name"] = name
            return "obj-123"

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "delete_network_object", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "network", "delete", "--uid", "obj-123"],
        )

        assert result.exit_code == 0
        assert "obj-123" in result.output
        assert "deleted successfully" in result.output
        assert captured["uid"] == "obj-123"
        assert captured["name"] is None

    def test_should_delete_by_uid_using_shortcut(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Delete command should work with -u shortcut."""
        captured: dict[str, Any] = {}

        def fake_delete(
            self: NetworkObjectService,
            uid: str | None = None,
            name: str | None = None,
        ) -> str:
            captured["uid"] = uid
            return uid or "obj-123"

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "delete_network_object", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "network", "delete", "-u", "obj-456"],
        )

        assert result.exit_code == 0
        assert captured["uid"] == "obj-456"


class TestNetworkDeleteByName:
    """Tests for deleting network objects by name."""

    def test_should_delete_by_name(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Delete command should successfully delete object by name."""
        captured: dict[str, Any] = {}

        def fake_delete(
            self: NetworkObjectService,
            uid: str | None = None,
            name: str | None = None,
        ) -> str:
            captured["uid"] = uid
            captured["name"] = name
            return "resolved-uid-789"

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "delete_network_object", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "network", "delete", "--name", "test-object"],
        )

        assert result.exit_code == 0
        assert "test-object" in result.output
        assert "resolved-uid-789" in result.output
        assert "deleted successfully" in result.output
        assert captured["uid"] is None
        assert captured["name"] == "test-object"

    def test_should_delete_by_name_using_shortcut(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Delete command should work with -n shortcut."""
        captured: dict[str, Any] = {}

        def fake_delete(
            self: NetworkObjectService,
            uid: str | None = None,
            name: str | None = None,
        ) -> str:
            captured["name"] = name
            return "uid-123"

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "delete_network_object", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "network", "delete", "-n", "my-object"],
        )

        assert result.exit_code == 0
        assert captured["name"] == "my-object"

    def test_should_handle_object_not_found(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Delete command should show error when object name is not found."""

        def fake_delete(
            self: NetworkObjectService,
            uid: str | None = None,
            name: str | None = None,
        ) -> str:
            raise NotFoundError("Network object with name 'missing-object' not found.")

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "delete_network_object", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "network", "delete", "--name", "missing-object"],
        )

        assert result.exit_code != 0
        assert "not found" in result.output


class TestNetworkDeleteValidation:
    """Tests for delete command parameter validation."""

    def test_should_fail_when_no_identifier_provided(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Delete command should fail when neither uid nor name is provided."""
        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            ["objects", "network", "delete"],
        )

        assert result.exit_code != 0
        assert "Either --uid or --name must be provided" in result.output

    def test_should_fail_when_both_identifiers_provided(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Delete command should fail when both uid and name are provided."""
        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            ["objects", "network", "delete", "--uid", "obj-123", "--name", "test"],
        )

        assert result.exit_code != 0
        assert "Only one of --uid or --name should be provided" in result.output


class TestNetworkObjectServiceDelete:
    """Tests for NetworkObjectService.delete_network_object method."""

    def test_delete_by_uid_calls_api(self, monkeypatch: MonkeyPatch) -> None:
        """Service should call API with correct uid parameter."""
        mock_api = Mock()

        get_response = Mock()
        get_response.status = 200
        get_response.read.return_value = json.dumps(SAMPLE_OBJECT.to_dict()).encode("utf-8")
        mock_api.get_object_without_preload_content.return_value = get_response

        delete_response = Mock()
        delete_response.read.return_value = b""
        delete_response.status = 200
        mock_api.delete_object_without_preload_content.return_value = delete_response

        service = NetworkObjectService.__new__(NetworkObjectService)
        service._object_api = mock_api

        result = service.delete_network_object(uid="test-uid")

        assert result == "test-uid"
        mock_api.get_object_without_preload_content.assert_called_once_with(uid="test-uid")
        mock_api.delete_object_without_preload_content.assert_called_once_with(uid="test-uid")

    def test_delete_by_name_resolves_to_uid(self, monkeypatch: MonkeyPatch) -> None:
        """Service should resolve name to uid before deleting."""
        mock_api = Mock()
        mock_response = Mock()
        mock_response.read.return_value = b""
        mock_response.status = 200
        mock_api.delete_object_without_preload_content.return_value = mock_response

        def fake_get_by_name(self: NetworkObjectService, name: str) -> NetworkObjectResponse:
            return SAMPLE_OBJECT

        service = NetworkObjectService.__new__(NetworkObjectService)
        service._object_api = mock_api
        monkeypatch.setattr(NetworkObjectService, "get_network_object_by_name", fake_get_by_name)

        result = service.delete_network_object(name="test-network")

        assert result == "obj-123"
        mock_api.delete_object_without_preload_content.assert_called_once_with(uid="obj-123")

    def test_delete_raises_error_when_name_not_found(self, monkeypatch: MonkeyPatch) -> None:
        """Service should raise NotFoundError when name doesn't exist."""

        def fake_get_by_name(self: NetworkObjectService, name: str) -> None:
            return None

        service = NetworkObjectService.__new__(NetworkObjectService)
        service._object_api = Mock()
        monkeypatch.setattr(NetworkObjectService, "get_network_object_by_name", fake_get_by_name)

        with pytest.raises(NotFoundError, match="not found"):
            service.delete_network_object(name="missing")

    def test_delete_validates_parameters(self) -> None:
        """Service should validate that exactly one parameter is provided."""
        service = NetworkObjectService.__new__(NetworkObjectService)

        with pytest.raises(ValueError, match="must be provided"):
            service.delete_network_object()

        with pytest.raises(ValueError, match="Only one"):
            service.delete_network_object(uid="uid-123", name="name-123")

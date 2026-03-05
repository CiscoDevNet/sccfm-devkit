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
from sccfm_core.services.object_management.object_api_helper import ObjectApiHelper

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

UPDATED_OBJECT = NetworkObjectResponse(
    uid="obj-123",
    name="renamed-network",
    description="Updated description",
    elements=["192.168.1.0/24"],
    labels=["production"],
    tags={"env": ["prod"]},
    object_type="NETWORK_OBJECT",
    literal="192.168.1.0/24",
)


def _stub_init(self: NetworkObjectService, config: Any) -> None:
    return None


class TestNetworkUpdateByUID:
    """Tests for updating network objects by UID."""

    def test_should_update_value_by_uid(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_update(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
            captured.update(kwargs)
            return UPDATED_OBJECT

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "update_network_object", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network",
                "update",
                "--uid",
                "obj-123",
                "--value",
                "192.168.1.0/24",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert captured["uid"] == "obj-123"
        assert captured["value"] == "192.168.1.0/24"
        payload = json.loads(result.output)
        assert payload["uid"] == "obj-123"
        assert payload["literal"] == "192.168.1.0/24"

    def test_should_update_name_by_uid(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_update(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
            captured.update(kwargs)
            return UPDATED_OBJECT

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "update_network_object", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network",
                "update",
                "--uid",
                "obj-123",
                "--new-name",
                "renamed-network",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert captured["uid"] == "obj-123"
        assert captured["new_name"] == "renamed-network"

    def test_should_update_multiple_fields(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_update(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
            captured.update(kwargs)
            return UPDATED_OBJECT

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "update_network_object", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network",
                "update",
                "--uid",
                "obj-123",
                "--new-name",
                "renamed-network",
                "--value",
                "192.168.1.0/24",
                "--description",
                "Updated description",
                "--labels",
                "production",
                "--tags",
                "env=prod",
            ],
        )

        assert result.exit_code == 0
        assert captured["new_name"] == "renamed-network"
        assert captured["value"] == "192.168.1.0/24"
        assert captured["description"] == "Updated description"
        assert captured["labels"] == ["production"]
        assert captured["tags"] == {"env": ["prod"]}


class TestNetworkUpdateByName:
    """Tests for updating network objects by name."""

    def test_should_update_by_name(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_update(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
            captured.update(kwargs)
            return UPDATED_OBJECT

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "update_network_object", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network",
                "update",
                "--name",
                "test-network",
                "--value",
                "192.168.1.0/24",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert captured["name"] == "test-network"
        assert captured["uid"] is None
        assert captured["value"] == "192.168.1.0/24"

    def test_should_handle_object_not_found(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_update(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
            raise NotFoundError("Network object with name 'missing' not found.")

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "update_network_object", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network",
                "update",
                "--name",
                "missing",
                "--value",
                "10.0.0.1",
            ],
        )

        assert result.exit_code != 0
        assert "not found" in result.output


class TestNetworkUpdateValidation:
    """Tests for update command parameter validation."""

    def test_should_fail_when_no_identifier_provided(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network",
                "update",
                "--value",
                "10.0.0.1",
            ],
        )

        assert result.exit_code != 0
        assert "Either --uid or --name must be provided" in result.output

    def test_should_fail_when_both_identifiers_provided(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network",
                "update",
                "--uid",
                "obj-123",
                "--name",
                "test",
                "--value",
                "10.0.0.1",
            ],
        )

        assert result.exit_code != 0
        assert "Only one of --uid or --name should be provided" in result.output

    def test_should_fail_when_no_update_fields_provided(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network",
                "update",
                "--uid",
                "obj-123",
            ],
        )

        assert result.exit_code != 0
        assert "At least one update field must be provided" in result.output


class TestNetworkUpdateOutput:
    """Tests for update command output rendering."""

    def test_should_display_table_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_update(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
            return UPDATED_OBJECT

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "update_network_object", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network",
                "update",
                "--uid",
                "obj-123",
                "--value",
                "192.168.1.0/24",
            ],
        )

        assert result.exit_code == 0
        assert "Network Object" in result.output
        assert "obj-123" in result.output
        assert "renamed-network" in result.output
        assert "updated" in result.output.lower()

    def test_should_display_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_update(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
            return UPDATED_OBJECT

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "update_network_object", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network",
                "update",
                "--uid",
                "obj-123",
                "--value",
                "192.168.1.0/24",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["uid"] == "obj-123"
        assert payload["name"] == "renamed-network"
        assert payload["literal"] == "192.168.1.0/24"


class TestNetworkUpdateErrors:
    """Tests for update command error handling."""

    def test_should_display_api_error(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        error_body = json.dumps(
            {
                "errorMsg": "Invalid value",
                "errorCode": "BAD_REQUEST",
                "details": {"value": "not-a-valid-ip"},
            }
        )

        def fake_update(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
            raise ApiException(status=400, body=error_body)

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "update_network_object", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network",
                "update",
                "--uid",
                "obj-123",
                "--value",
                "not-a-valid-ip",
            ],
        )

        assert result.exit_code != 0
        assert "Invalid value" in result.output
        assert "BAD_REQUEST" in result.output


class TestNetworkObjectServiceUpdate:
    """Unit tests for NetworkObjectService.update_network_object method."""

    def test_update_by_uid_calls_api(self, monkeypatch: MonkeyPatch) -> None:
        mock_api = Mock()

        raw_api_response = {
            "uid": "obj-123",
            "name": "test-network",
            "description": "Test object",
            "elements": ["10.0.0.0/24"],
            "labels": ["test"],
            "tags": {"env": ["test"]},
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "10.0.0.0/24"},
            },
        }
        get_response = Mock()
        get_response.status = 200
        get_response.read.return_value = json.dumps(raw_api_response).encode("utf-8")
        mock_api.get_object_without_preload_content.return_value = get_response

        modify_response = Mock()
        modify_response.read.return_value = json.dumps(
            {
                "uid": "test-uid",
                "name": "test-obj",
                "value": {
                    "objectType": "NETWORK_OBJECT",
                    "defaultContent": {"literal": "192.168.1.0/24"},
                },
            }
        ).encode("utf-8")
        modify_response.status = 200
        mock_api.modify_object_without_preload_content.return_value = modify_response

        service = NetworkObjectService.__new__(NetworkObjectService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        result = service.update_network_object(
            uid="test-uid",
            value="192.168.1.0/24",
        )

        assert result.uid == "test-uid"
        assert result.literal == "192.168.1.0/24"
        mock_api.get_object_without_preload_content.assert_called_once_with(uid="test-uid")
        mock_api.modify_object_without_preload_content.assert_called_once()
        call_kwargs = mock_api.modify_object_without_preload_content.call_args
        assert call_kwargs.kwargs["uid"] == "test-uid"

    def test_update_by_name_resolves_to_uid(self, monkeypatch: MonkeyPatch) -> None:
        mock_api = Mock()
        mock_response = Mock()
        mock_response.read.return_value = json.dumps(
            {
                "uid": "obj-123",
                "name": "renamed",
                "value": {
                    "objectType": "NETWORK_OBJECT",
                    "defaultContent": {"literal": "10.0.0.1"},
                },
            }
        ).encode("utf-8")
        mock_response.status = 200
        mock_api.modify_object_without_preload_content.return_value = mock_response

        def fake_get_by_name(self: NetworkObjectService, name: str) -> NetworkObjectResponse:
            return SAMPLE_OBJECT

        service = NetworkObjectService.__new__(NetworkObjectService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api
        monkeypatch.setattr(
            NetworkObjectService,
            "get_network_object_by_name",
            fake_get_by_name,
        )

        result = service.update_network_object(
            name="test-network",
            new_name="renamed",
        )

        assert result.uid == "obj-123"
        call_kwargs = mock_api.modify_object_without_preload_content.call_args
        assert call_kwargs.kwargs["uid"] == "obj-123"

    def test_update_raises_error_when_name_not_found(self, monkeypatch: MonkeyPatch) -> None:
        def fake_get_by_name(self: NetworkObjectService, name: str) -> NetworkObjectResponse | None:
            return None

        service = NetworkObjectService.__new__(NetworkObjectService)
        service._object_api = Mock()
        monkeypatch.setattr(
            NetworkObjectService,
            "get_network_object_by_name",
            fake_get_by_name,
        )

        with pytest.raises(NotFoundError, match="not found"):
            service.update_network_object(name="missing", value="10.0.0.1")

    def test_update_validates_parameters(self) -> None:
        service = NetworkObjectService.__new__(NetworkObjectService)

        with pytest.raises(ValueError, match="must be provided"):
            service.update_network_object(value="10.0.0.1")

        with pytest.raises(ValueError, match="Only one"):
            service.update_network_object(
                uid="uid-123",
                name="name-123",
                value="10.0.0.1",
            )


class TestCheck:
    """Tests for the --check flag on the update command."""

    def test_should_report_existing_object_by_uid(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Check flag should report when a network object exists (by UID)."""
        called: dict[str, bool] = {"update": False}

        def fake_get(self: NetworkObjectService, uid: str) -> NetworkObjectResponse:
            return SAMPLE_OBJECT

        def fake_update(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
            called["update"] = True
            return UPDATED_OBJECT

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "get_network_object", fake_get)
        monkeypatch.setattr(NetworkObjectService, "update_network_object", fake_update)

        result = cli_runner.invoke(
            cli,
            ["objects", "network", "update", "--check", "--uid", "obj-123"],
        )

        assert result.exit_code == 0
        assert "exists" in result.output
        assert "update can proceed" in result.output
        assert not called["update"]

    def test_should_report_existing_object_by_name(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Check flag should report when a network object exists (by name)."""
        called: dict[str, bool] = {"update": False}

        def fake_get_by_name(self: NetworkObjectService, name: str) -> NetworkObjectResponse:
            return SAMPLE_OBJECT

        def fake_update(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
            called["update"] = True
            return UPDATED_OBJECT

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "get_network_object_by_name", fake_get_by_name)
        monkeypatch.setattr(NetworkObjectService, "update_network_object", fake_update)

        result = cli_runner.invoke(
            cli,
            ["objects", "network", "update", "--check", "--name", "test-network"],
        )

        assert result.exit_code == 0
        assert "exists" in result.output
        assert "update can proceed" in result.output
        assert not called["update"]

    def test_should_report_missing_object(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Check flag should report when a network object is not found."""
        called: dict[str, bool] = {"update": False}

        def fake_get_by_name(self: NetworkObjectService, name: str) -> NetworkObjectResponse | None:
            return None

        def fake_update(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
            called["update"] = True
            return UPDATED_OBJECT

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "get_network_object_by_name", fake_get_by_name)
        monkeypatch.setattr(NetworkObjectService, "update_network_object", fake_update)

        result = cli_runner.invoke(
            cli,
            ["objects", "network", "update", "--check", "--name", "missing-object"],
        )

        assert result.exit_code == 0
        assert "not found" in result.output
        assert "update would fail" in result.output
        assert not called["update"]

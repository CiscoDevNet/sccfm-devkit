# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.models import Config
from cisco_sccfm_core.errors import NotFoundError
from cisco_sccfm_core.services import NetworkGroupService
from cisco_sccfm_core.services.object_management import NetworkGroupResponse

SAMPLE_GROUP = NetworkGroupResponse(
    uid="grp-123",
    name="test-network-group",
    description="Test group",
    elements=["10.0.0.0/24"],
    labels=["test"],
    tags={"env": ["test"]},
    object_type="NETWORK_GROUP",
    literals=[],
    referenced_object_uids=["ref-uid-001"],
)

UPDATED_GROUP = NetworkGroupResponse(
    uid="grp-123",
    name="renamed-group",
    description="Updated description",
    elements=["10.0.0.0/24", "192.168.1.0/24"],
    labels=["production"],
    tags={"env": ["prod"]},
    object_type="NETWORK_GROUP",
    literals=[],
    referenced_object_uids=["ref-uid-001", "ref-uid-002"],
)


def _stub_init(self: NetworkGroupService, config: Any) -> None:
    return None


class TestNetworkGroupUpdateByUID:
    """Tests for updating network group objects by UID."""

    def test_should_update_referenced_objects_by_uid(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_update(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
            captured.update(kwargs)
            return UPDATED_GROUP

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "update_network_group", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "update",
                "--uid",
                "grp-123",
                "--referenced-object",
                "ref-uid-001",
                "--referenced-object",
                "ref-uid-002",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert captured["uid"] == "grp-123"
        assert captured["referenced_objects"] == ["ref-uid-001", "ref-uid-002"]
        payload = json.loads(result.output)
        assert payload["uid"] == "grp-123"

    def test_should_update_name_by_uid(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_update(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
            captured.update(kwargs)
            return UPDATED_GROUP

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "update_network_group", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "update",
                "--uid",
                "grp-123",
                "--new-name",
                "renamed-group",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert captured["uid"] == "grp-123"
        assert captured["new_name"] == "renamed-group"

    def test_should_update_multiple_fields(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_update(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
            captured.update(kwargs)
            return UPDATED_GROUP

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "update_network_group", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "update",
                "--uid",
                "grp-123",
                "--new-name",
                "renamed-group",
                "--referenced-object",
                "ref-uid-001",
                "--description",
                "Updated description",
                "--labels",
                "production",
                "--tags",
                "env=prod",
            ],
        )

        assert result.exit_code == 0
        assert captured["new_name"] == "renamed-group"
        assert captured["referenced_objects"] == ["ref-uid-001"]
        assert captured["description"] == "Updated description"
        assert captured["labels"] == ["production"]
        assert captured["tags"] == {"env": ["prod"]}


class TestNetworkGroupUpdateByName:
    """Tests for updating network group objects by name."""

    def test_should_update_by_name(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_update(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
            captured.update(kwargs)
            return UPDATED_GROUP

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "update_network_group", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "update",
                "--name",
                "test-network-group",
                "--referenced-object",
                "ref-uid-002",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert captured["name"] == "test-network-group"
        assert captured["uid"] is None
        assert captured["referenced_objects"] == ["ref-uid-002"]

    def test_should_handle_group_not_found(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_update(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
            raise NotFoundError("Network group with name 'missing' not found.")

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "update_network_group", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "update",
                "--name",
                "missing",
                "--referenced-object",
                "ref-uid-001",
            ],
        )

        assert result.exit_code != 0
        assert "not found" in result.output


class TestNetworkGroupUpdateValidation:
    """Tests for update command parameter validation."""

    def test_should_fail_when_no_identifier_provided(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "update",
                "--referenced-object",
                "ref-uid-001",
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
        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "update",
                "--uid",
                "grp-123",
                "--name",
                "test-group",
                "--referenced-object",
                "ref-uid-001",
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
        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "update",
                "--uid",
                "grp-123",
            ],
        )

        assert result.exit_code != 0
        assert "At least one update field must be provided" in result.output


class TestNetworkGroupUpdateOutput:
    """Tests for update command output rendering."""

    def test_should_display_table_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_update(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
            return UPDATED_GROUP

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "update_network_group", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "update",
                "--uid",
                "grp-123",
                "--referenced-object",
                "ref-uid-001",
            ],
        )

        assert result.exit_code == 0
        assert "grp-123" in result.output
        assert "renamed-group" in result.output
        assert "NETWORK_GROUP" in result.output
        assert "Updated description" in result.output
        assert "production" in result.output
        assert "updated" in result.output.lower()

    def test_should_display_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_update(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
            return UPDATED_GROUP

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "update_network_group", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "update",
                "--uid",
                "grp-123",
                "--referenced-object",
                "ref-uid-001",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["uid"] == "grp-123"
        assert payload["name"] == "renamed-group"
        assert payload["referenced_object_uids"] == ["ref-uid-001", "ref-uid-002"]


class TestCheck:
    """Tests for the --check flag on the update command."""

    def test_should_report_existing_group_by_uid(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Check flag should report when a network group exists (by UID)."""
        called: dict[str, bool] = {"update": False}

        def fake_get(self: NetworkGroupService, uid: str) -> NetworkGroupResponse:
            return SAMPLE_GROUP

        def fake_update(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
            called["update"] = True
            return UPDATED_GROUP

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "get_network_group", fake_get)
        monkeypatch.setattr(NetworkGroupService, "update_network_group", fake_update)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "update", "--check", "--uid", "grp-123"],
        )

        assert result.exit_code == 0
        assert "exists" in result.output
        assert "update can proceed" in result.output
        assert not called["update"]

    def test_should_report_existing_group_by_name(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Check flag should report when a network group exists (by name)."""
        called: dict[str, bool] = {"update": False}

        def fake_get_by_name(self: NetworkGroupService, name: str) -> NetworkGroupResponse:
            return SAMPLE_GROUP

        def fake_update(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
            called["update"] = True
            return UPDATED_GROUP

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "get_network_group_by_name", fake_get_by_name)
        monkeypatch.setattr(NetworkGroupService, "update_network_group", fake_update)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "update", "--check", "--name", "test-network-group"],
        )

        assert result.exit_code == 0
        assert "exists" in result.output
        assert "update can proceed" in result.output
        assert not called["update"]

    def test_should_report_missing_group(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Check flag should report when a network group is not found."""
        called: dict[str, bool] = {"update": False}

        def fake_get_by_name(self: NetworkGroupService, name: str) -> NetworkGroupResponse | None:
            return None

        def fake_update(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
            called["update"] = True
            return UPDATED_GROUP

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "get_network_group_by_name", fake_get_by_name)
        monkeypatch.setattr(NetworkGroupService, "update_network_group", fake_update)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "update", "--check", "--name", "missing-group"],
        )

        assert result.exit_code == 0
        assert "not found" in result.output
        assert "update would fail" in result.output
        assert not called["update"]

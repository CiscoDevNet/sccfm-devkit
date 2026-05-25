# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.errors import NotFoundError
from sccfm_core.services import NetworkGroupService
from sccfm_core.services.object_management import NetworkObjectResponse

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


def _stub_init(self: NetworkGroupService, config: Any) -> None:
    return None


class TestNetworkGroupDeleteByUID:
    """Tests for deleting network group objects by UID."""

    def test_should_delete_by_uid(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Delete command should successfully delete group by UID."""
        captured: dict[str, Any] = {}

        def fake_delete(
            self: NetworkGroupService,
            uid: str | None = None,
            name: str | None = None,
        ) -> str:
            captured["uid"] = uid
            captured["name"] = name
            return "grp-123"

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "delete_network_group", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "delete", "--uid", "grp-123"],
        )

        assert result.exit_code == 0
        assert "grp-123" in result.output
        assert "deleted successfully" in result.output
        assert captured["uid"] == "grp-123"
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
            self: NetworkGroupService,
            uid: str | None = None,
            name: str | None = None,
        ) -> str:
            captured["uid"] = uid
            return uid or "grp-123"

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "delete_network_group", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "delete", "-u", "grp-456"],
        )

        assert result.exit_code == 0
        assert captured["uid"] == "grp-456"


class TestNetworkGroupDeleteByName:
    """Tests for deleting network group objects by name."""

    def test_should_delete_by_name(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Delete command should successfully delete group by name."""
        captured: dict[str, Any] = {}

        def fake_delete(
            self: NetworkGroupService,
            uid: str | None = None,
            name: str | None = None,
        ) -> str:
            captured["uid"] = uid
            captured["name"] = name
            return "resolved-uid-789"

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "delete_network_group", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "delete", "--name", "test-group"],
        )

        assert result.exit_code == 0
        assert "test-group" in result.output
        assert "resolved-uid-789" in result.output
        assert "deleted successfully" in result.output
        assert captured["uid"] is None
        assert captured["name"] == "test-group"

    def test_should_delete_by_name_using_shortcut(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Delete command should work with -n shortcut."""
        captured: dict[str, Any] = {}

        def fake_delete(
            self: NetworkGroupService,
            uid: str | None = None,
            name: str | None = None,
        ) -> str:
            captured["name"] = name
            return "uid-123"

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "delete_network_group", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "delete", "-n", "my-group"],
        )

        assert result.exit_code == 0
        assert captured["name"] == "my-group"

    def test_should_handle_group_not_found(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Delete command should show error when group name is not found."""

        def fake_delete(
            self: NetworkGroupService,
            uid: str | None = None,
            name: str | None = None,
        ) -> str:
            raise NotFoundError("Network group with name 'missing-group' not found.")

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "delete_network_group", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "delete", "--name", "missing-group"],
        )

        assert result.exit_code != 0
        assert "not found" in result.output


class TestNetworkGroupDeleteValidation:
    """Tests for delete command parameter validation."""

    def test_should_fail_when_no_identifier_provided(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Delete command should fail when neither uid nor name is provided."""
        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "delete"],
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
        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "delete",
                "--uid",
                "grp-123",
                "--name",
                "test",
            ],
        )

        assert result.exit_code != 0
        assert "Only one of --uid or --name should be provided" in result.output


class TestCheck:
    """Tests for the --check flag on the delete command."""

    def test_should_report_existing_group_by_uid(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Check flag should report when a network group exists (by UID)."""
        called: dict[str, bool] = {"delete": False}

        def fake_get(self: NetworkGroupService, uid: str) -> NetworkObjectResponse:
            return SAMPLE_GROUP

        def fake_delete(
            self: NetworkGroupService,
            uid: str | None = None,
            name: str | None = None,
        ) -> str:
            called["delete"] = True
            return uid or ""

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "get_network_group", fake_get)
        monkeypatch.setattr(NetworkGroupService, "delete_network_group", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "delete", "--check", "--uid", "grp-123"],
        )

        assert result.exit_code == 0
        assert "exists" in result.output
        assert "delete can proceed" in result.output
        assert not called["delete"]

    def test_should_report_existing_group_by_name(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Check flag should report when a network group exists (by name)."""
        called: dict[str, bool] = {"delete": False}

        def fake_get_by_name(self: NetworkGroupService, name: str) -> NetworkObjectResponse:
            return SAMPLE_GROUP

        def fake_delete(
            self: NetworkGroupService,
            uid: str | None = None,
            name: str | None = None,
        ) -> str:
            called["delete"] = True
            return uid or ""

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "get_network_group_by_name", fake_get_by_name)
        monkeypatch.setattr(NetworkGroupService, "delete_network_group", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "delete", "--check", "--name", "test-network-group"],
        )

        assert result.exit_code == 0
        assert "exists" in result.output
        assert "delete can proceed" in result.output
        assert not called["delete"]

    def test_should_report_missing_group(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Check flag should report when a network group is not found."""
        called: dict[str, bool] = {"delete": False}

        def fake_get_by_name(self: NetworkGroupService, name: str) -> NetworkObjectResponse | None:
            return None

        def fake_delete(
            self: NetworkGroupService,
            uid: str | None = None,
            name: str | None = None,
        ) -> str:
            called["delete"] = True
            return uid or ""

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "get_network_group_by_name", fake_get_by_name)
        monkeypatch.setattr(NetworkGroupService, "delete_network_group", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "delete", "--check", "--name", "missing-group"],
        )

        assert result.exit_code == 0
        assert "not found" in result.output
        assert "delete would fail" in result.output
        assert not called["delete"]

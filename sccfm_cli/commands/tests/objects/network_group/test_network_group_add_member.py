from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.errors import NotFoundError
from sccfm_core.services import NetworkGroupService
from sccfm_core.services.object_management import (
    NetworkGroupMemberMutationResult,
    NetworkGroupResponse,
)

CURRENT_GROUP = NetworkGroupResponse(
    uid="grp-123",
    name="test-network-group",
    description="Test group",
    elements=["10.0.0.0/24"],
    labels=["test"],
    tags={"env": ["test"]},
    object_type="NETWORK_GROUP",
    literals=["10.0.0.0/24"],
    referenced_object_uids=["ref-uid-001"],
)

UPDATED_GROUP = NetworkGroupResponse(
    uid="grp-123",
    name="test-network-group",
    description="Test group",
    elements=["10.0.0.0/24", "10.0.1.0/24"],
    labels=["test"],
    tags={"env": ["test"]},
    object_type="NETWORK_GROUP",
    literals=["10.0.0.0/24"],
    referenced_object_uids=["ref-uid-001", "ref-uid-002"],
)


def _stub_init(self: NetworkGroupService, config: Any) -> None:
    return None


class TestNetworkGroupAddMemberCommand:
    def test_should_add_members_by_uid(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_add(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupMemberMutationResult:
            captured.update(kwargs)
            return NetworkGroupMemberMutationResult(network_group=UPDATED_GROUP, changed=True)

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "add_network_group_members", fake_add)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "add-member",
                "--uid",
                "grp-123",
                "--referenced-object",
                "ref-uid-002",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert captured["uid"] == "grp-123"
        assert captured["referenced_objects"] == ["ref-uid-002"]
        payload = json.loads(result.output)
        assert payload["referenced_object_uids"] == ["ref-uid-001", "ref-uid-002"]

    def test_should_report_noop_when_members_already_present(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_add(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupMemberMutationResult:
            return NetworkGroupMemberMutationResult(network_group=CURRENT_GROUP, changed=False)

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "add_network_group_members", fake_add)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "add-member",
                "--name",
                "test-network-group",
                "--referenced-object",
                "ref-uid-001",
            ],
        )

        assert result.exit_code == 0
        assert "already contains all requested members" in result.output

    def test_should_require_referenced_object(
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
                "add-member",
                "--name",
                "test-network-group",
            ],
        )

        assert result.exit_code != 0
        assert "At least one --referenced-object must be provided." in result.output

    def test_should_handle_group_not_found(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_add(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupMemberMutationResult:
            raise NotFoundError("Network group with name 'missing' not found.")

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "add_network_group_members", fake_add)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "add-member",
                "--name",
                "missing",
                "--referenced-object",
                "ref-uid-001",
            ],
        )

        assert result.exit_code != 0
        assert "Network group with name 'missing' not found." in result.output

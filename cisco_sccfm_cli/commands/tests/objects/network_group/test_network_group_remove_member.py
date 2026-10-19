# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.models import Config
from cisco_sccfm_core.errors import NotFoundError
from cisco_sccfm_core.services import NetworkGroupService, NetworkObjectService
from cisco_sccfm_core.services.object_management import (
    NetworkGroupMemberMutationResult,
    NetworkGroupResponse,
    NetworkObjectResponse,
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
    elements=["10.0.0.0/24"],
    labels=["test"],
    tags={"env": ["test"]},
    object_type="NETWORK_GROUP",
    literals=["10.0.0.0/24"],
    referenced_object_uids=[],
)


def _stub_init(self: NetworkGroupService, config: Any) -> None:
    return None


def _stub_obj_init(self: NetworkObjectService, config: Any) -> None:
    return None


class TestNetworkGroupRemoveMemberCommand:
    def test_should_remove_members_by_name(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_remove(
            self: NetworkGroupService, **kwargs: Any
        ) -> NetworkGroupMemberMutationResult:
            captured.update(kwargs)
            return NetworkGroupMemberMutationResult(network_group=UPDATED_GROUP, changed=True)

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "remove_network_group_members", fake_remove)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "remove-member",
                "--name",
                "test-network-group",
                "--referenced-object",
                "ref-uid-001",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert captured["name"] == "test-network-group"
        assert captured["referenced_objects"] == ["ref-uid-001"]
        payload = json.loads(result.output)
        assert payload["referenced_object_uids"] == []

    def test_should_report_noop_when_members_are_already_absent(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_remove(
            self: NetworkGroupService, **kwargs: Any
        ) -> NetworkGroupMemberMutationResult:
            return NetworkGroupMemberMutationResult(network_group=CURRENT_GROUP, changed=False)

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "remove_network_group_members", fake_remove)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "remove-member",
                "--uid",
                "grp-123",
                "--referenced-object",
                "ref-uid-002",
            ],
        )

        assert result.exit_code == 0
        assert "already excludes all requested members" in result.output

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
                "remove-member",
                "--uid",
                "grp-123",
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
        def fake_remove(
            self: NetworkGroupService, **kwargs: Any
        ) -> NetworkGroupMemberMutationResult:
            raise NotFoundError("Network group with UID 'grp-123' not found.")

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "remove_network_group_members", fake_remove)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "remove-member",
                "--uid",
                "grp-123",
                "--referenced-object",
                "ref-uid-001",
            ],
        )

        assert result.exit_code != 0
        assert "Network group with UID 'grp-123' not found." in result.output

    def test_check_should_validate_referenced_objects(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_get_group(self: NetworkGroupService, uid: str) -> NetworkGroupResponse | None:
            return CURRENT_GROUP

        obj_response = NetworkObjectResponse(
            uid="obj-uid-001",
            name="web-server-01",
            description=None,
            elements=[],
            labels=[],
            tags={},
            object_type="NETWORK_OBJECT",
            literal="10.0.1.100",
        )

        def fake_get_obj_by_name(
            self: NetworkObjectService, name: str
        ) -> NetworkObjectResponse | None:
            if name == "web-server-01":
                return obj_response
            return None

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "get_network_group", fake_get_group)
        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_obj_init)
        monkeypatch.setattr(
            NetworkObjectService, "get_network_object_by_name", fake_get_obj_by_name
        )

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "remove-member",
                "--uid",
                "grp-123",
                "--referenced-object",
                "web-server-01",
                "--referenced-object",
                "does-not-exist",
                "--check",
            ],
        )

        assert result.exit_code == 0
        assert "Referenced object 'web-server-01' exists" in result.output
        assert "Referenced object 'does-not-exist' not found." in result.output

    def test_check_json_should_emit_single_payload_with_referenced_object_results(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_get_group(self: NetworkGroupService, uid: str) -> NetworkGroupResponse | None:
            return CURRENT_GROUP

        obj_response = NetworkObjectResponse(
            uid="11111111-1111-1111-1111-111111111111",
            name="web-server-01",
            description=None,
            elements=[],
            labels=[],
            tags={},
            object_type="NETWORK_OBJECT",
            literal="10.0.1.100",
        )

        def fake_get_obj_by_name(
            self: NetworkObjectService, name: str
        ) -> NetworkObjectResponse | None:
            if name == "web-server-01":
                return obj_response
            return None

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "get_network_group", fake_get_group)
        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_obj_init)
        monkeypatch.setattr(
            NetworkObjectService, "get_network_object_by_name", fake_get_obj_by_name
        )

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "network-group",
                "remove-member",
                "--uid",
                "grp-123",
                "--referenced-object",
                "web-server-01",
                "--referenced-object",
                "does-not-exist",
                "--check",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["target"]["exists"] is True
        assert payload["referenced_objects"] == [
            {
                "identifier": "web-server-01",
                "exists": True,
                "uid": "11111111-1111-1111-1111-111111111111",
            },
            {
                "identifier": "does-not-exist",
                "exists": False,
                "uid": None,
            },
        ]

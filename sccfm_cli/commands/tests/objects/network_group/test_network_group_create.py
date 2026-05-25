# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk.exceptions import ApiException

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services import NetworkGroupService
from sccfm_core.services.object_management import NetworkGroupResponse

SAMPLE_RESPONSE = NetworkGroupResponse(
    uid="grp-abc-123",
    name="my-network-group",
    description="Test network group",
    elements=[],
    labels=["production"],
    tags={"env": ["prod"]},
    object_type="NETWORK_GROUP",
    literals=["10.10.0.0/24", "192.168.1.0/24"],
    referenced_object_uids=["uid-member-1", "uid-member-2"],
)


def _stub_init(self: NetworkGroupService, config: Any) -> None:
    return None


def test_should_create_network_group_with_json_output(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """Create command should return valid JSON when format is json."""
    captured: dict[str, Any] = {}

    def fake_create(
        self: NetworkGroupService,
        *,
        name: str,
        network_literals: list[str] | None = None,
        url_literals: list[str] | None = None,
        referenced_objects: list[str] | None = None,
        description: str | None = None,
        labels: list[str] | None = None,
        tags: dict[str, list[str]] | None = None,
    ) -> NetworkGroupResponse:
        captured["name"] = name
        captured["network_literals"] = network_literals
        captured["url_literals"] = url_literals
        captured["referenced_objects"] = referenced_objects
        captured["description"] = description
        captured["labels"] = labels
        captured["tags"] = tags
        return SAMPLE_RESPONSE

    monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkGroupService, "create_network_group", fake_create)

    result = cli_runner.invoke(
        cli,
        [
            "objects",
            "network-group",
            "create",
            "--name",
            "my-network-group",
            "--referenced-object",
            "uid-member-1",
            "--referenced-object",
            "uid-member-2",
            "--network-literal",
            "10.10.0.0/24",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["uid"] == "grp-abc-123"
    assert payload["name"] == "my-network-group"
    assert payload["object_type"] == "NETWORK_GROUP"
    assert payload["literals"] == ["10.10.0.0/24", "192.168.1.0/24"]
    assert payload["referenced_object_uids"] == ["uid-member-1", "uid-member-2"]
    assert captured["name"] == "my-network-group"
    assert captured["referenced_objects"] == ["uid-member-1", "uid-member-2"]
    assert captured["network_literals"] == ["10.10.0.0/24"]


def test_should_display_table_output(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """Create command should display a table by default."""

    def fake_create(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
        return SAMPLE_RESPONSE

    monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkGroupService, "create_network_group", fake_create)

    result = cli_runner.invoke(
        cli,
        [
            "objects",
            "network-group",
            "create",
            "--name",
            "my-network-group",
            "--referenced-object",
            "uid-member-1",
        ],
    )

    assert result.exit_code == 0
    assert "created" in result.output.lower()
    assert "grp-abc-123" in result.output
    assert "my-network-group" in result.output
    assert "NETWORK_GROUP" in result.output


def test_should_pass_tags_and_labels(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """Create command should parse --tags and --labels correctly."""
    captured: dict[str, Any] = {}

    def fake_create(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
        captured.update(kwargs)
        return SAMPLE_RESPONSE

    monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkGroupService, "create_network_group", fake_create)

    result = cli_runner.invoke(
        cli,
        [
            "objects",
            "network-group",
            "create",
            "--name",
            "my-network-group",
            "--network-literal",
            "10.0.0.0/8",
            "--tags",
            "env=prod,staging",
            "--labels",
            "migration",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["tags"] == {"env": ["prod", "staging"]}
    assert captured["labels"] == ["migration"]


def test_should_display_api_error(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """Create command should display API errors for duplicate groups."""
    error_body = json.dumps(
        {
            "errorMsg": "Object already exists",
            "errorCode": "CONFLICT",
            "details": {"name": "my-network-group"},
        }
    )

    def fake_create(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
        raise ApiException(status=409, body=error_body)

    monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkGroupService, "create_network_group", fake_create)

    result = cli_runner.invoke(
        cli,
        [
            "objects",
            "network-group",
            "create",
            "--name",
            "my-network-group",
            "--network-literal",
            "10.0.0.0/8",
        ],
    )

    assert result.exit_code != 0
    assert "Object already exists" in result.output
    assert "CONFLICT" in result.output


def test_should_create_with_only_literals(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """Create command should work with only network literal values (no referenced objects)."""
    captured: dict[str, Any] = {}

    def fake_create(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
        captured.update(kwargs)
        return SAMPLE_RESPONSE

    monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkGroupService, "create_network_group", fake_create)

    result = cli_runner.invoke(
        cli,
        [
            "objects",
            "network-group",
            "create",
            "--name",
            "literals-only",
            "--network-literal",
            "10.0.0.0/8",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["name"] == "literals-only"
    assert captured["network_literals"] == ["10.0.0.0/8"]
    assert captured["referenced_objects"] is None


def test_should_create_with_only_referenced_objects(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """Create command should work with only referenced object UIDs (no literals)."""
    captured: dict[str, Any] = {}

    def fake_create(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
        captured.update(kwargs)
        return SAMPLE_RESPONSE

    monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkGroupService, "create_network_group", fake_create)

    result = cli_runner.invoke(
        cli,
        [
            "objects",
            "network-group",
            "create",
            "--name",
            "refs-only",
            "--referenced-object",
            "uid-abc",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["name"] == "refs-only"
    assert captured["referenced_objects"] == ["uid-abc"]
    assert captured["network_literals"] is None


def test_should_fail_when_no_referenced_objects_or_literals(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """Create command should fail when neither --referenced-object nor --*-literal is provided."""
    monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)

    result = cli_runner.invoke(
        cli,
        [
            "objects",
            "network-group",
            "create",
            "--name",
            "empty-group",
        ],
    )

    assert result.exit_code != 0
    assert "At least one --referenced-object" in result.output


def test_should_fail_when_both_literal_types_provided(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """Create command should fail when both --network-literal and --url-literal are given."""
    monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)

    result = cli_runner.invoke(
        cli,
        [
            "objects",
            "network-group",
            "create",
            "--name",
            "mixed-literals",
            "--network-literal",
            "10.0.0.0/8",
            "--url-literal",
            "https://example.com",
        ],
    )

    assert result.exit_code != 0
    assert "Only one literal type" in result.output


def test_should_create_with_url_literals(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """Create command should work with --url-literal."""
    captured: dict[str, Any] = {}

    def fake_create(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
        captured.update(kwargs)
        return SAMPLE_RESPONSE

    monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkGroupService, "create_network_group", fake_create)

    result = cli_runner.invoke(
        cli,
        [
            "objects",
            "network-group",
            "create",
            "--name",
            "url-group",
            "--url-literal",
            "https://example.com",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["name"] == "url-group"
    assert captured["url_literals"] == ["https://example.com"]
    assert captured["network_literals"] is None


class TestCheck:
    """Tests for the --check flag on the create command."""

    def test_should_report_existing_group(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Check flag should report when a network group already exists."""
        called: dict[str, bool] = {"create": False}

        def fake_get_by_name(self: NetworkGroupService, name: str) -> NetworkGroupResponse:
            return SAMPLE_RESPONSE

        def fake_create(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
            called["create"] = True
            return SAMPLE_RESPONSE

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "get_network_group_by_name", fake_get_by_name)
        monkeypatch.setattr(NetworkGroupService, "create_network_group", fake_create)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "create", "--check", "--name", "my-network-group"],
        )

        assert result.exit_code == 0
        assert "already exists" in result.output
        assert "create would fail" in result.output
        assert not called["create"]

    def test_should_report_missing_group(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Check flag should report when a network group does not exist."""
        called: dict[str, bool] = {"create": False}

        def fake_get_by_name(self: NetworkGroupService, name: str) -> NetworkGroupResponse | None:
            return None

        def fake_create(self: NetworkGroupService, **kwargs: Any) -> NetworkGroupResponse:
            called["create"] = True
            return SAMPLE_RESPONSE

        monkeypatch.setattr(NetworkGroupService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkGroupService, "get_network_group_by_name", fake_get_by_name)
        monkeypatch.setattr(NetworkGroupService, "create_network_group", fake_create)

        result = cli_runner.invoke(
            cli,
            ["objects", "network-group", "create", "--check", "--name", "no-such-group"],
        )

        assert result.exit_code == 0
        assert "not found" in result.output
        assert "create can proceed" in result.output
        assert not called["create"]

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk.exceptions import ApiException

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.models import Config
from cisco_sccfm_core.services import NetworkObjectService
from cisco_sccfm_core.services.object_management import NetworkObjectResponse

SAMPLE_RESPONSE = NetworkObjectResponse(
    uid="abc-123",
    name="my-network",
    description="Test network",
    elements=["10.10.0.0/24"],
    labels=["production"],
    tags={"env": ["prod"]},
    object_type="NETWORK_OBJECT",
    literal="10.10.0.0/24",
)


def _stub_init(self: NetworkObjectService, config: Any) -> None:
    return None


def test_should_create_network_object_with_json_output(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """Create command should return valid JSON when format is json."""
    captured: dict[str, Any] = {}

    def fake_create(
        self: NetworkObjectService,
        *,
        name: str,
        value: str,
        description: str | None = None,
        labels: list[str] | None = None,
        tags: dict[str, list[str]] | None = None,
    ) -> NetworkObjectResponse:
        captured["name"] = name
        captured["value"] = value
        captured["description"] = description
        captured["labels"] = labels
        captured["tags"] = tags
        return SAMPLE_RESPONSE

    monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkObjectService, "create_network_object", fake_create)

    result = cli_runner.invoke(
        cli,
        [
            "objects",
            "network",
            "create",
            "--name",
            "my-network",
            "--value",
            "10.10.0.0/24",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["uid"] == "abc-123"
    assert payload["name"] == "my-network"
    assert payload["object_type"] == "NETWORK_OBJECT"
    assert payload["literal"] == "10.10.0.0/24"
    assert captured["name"] == "my-network"
    assert captured["value"] == "10.10.0.0/24"


def test_should_display_table_output(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """Create command should display a table by default."""

    def fake_create(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
        return SAMPLE_RESPONSE

    monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkObjectService, "create_network_object", fake_create)

    result = cli_runner.invoke(
        cli,
        ["objects", "network", "create", "--name", "my-network", "--value", "10.10.0.0/24"],
    )

    assert result.exit_code == 0
    assert "Network Object" in result.output
    assert "abc-123" in result.output
    assert "my-network" in result.output
    assert "NETWORK_OBJECT" in result.output


def test_should_pass_tags_and_labels(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """Create command should parse --tags and --labels correctly."""
    captured: dict[str, Any] = {}

    def fake_create(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
        captured.update(kwargs)
        return SAMPLE_RESPONSE

    monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkObjectService, "create_network_object", fake_create)

    result = cli_runner.invoke(
        cli,
        [
            "objects",
            "network",
            "create",
            "--name",
            "my-network",
            "--value",
            "10.10.0.0/24",
            "--tags",
            "env=prod,staging",
            "--tags",
            "production",
            "--labels",
            "migration",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["tags"] == {"env": ["prod", "staging"], "labels": ["production"]}
    assert captured["labels"] == ["migration"]


def test_should_display_api_error(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """Create command should display API errors for duplicate objects."""
    error_body = json.dumps(
        {
            "errorMsg": "Object already exists",
            "errorCode": "CONFLICT",
            "details": {"name": "my-network"},
        }
    )

    def fake_create(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
        raise ApiException(status=409, body=error_body)

    monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkObjectService, "create_network_object", fake_create)

    result = cli_runner.invoke(
        cli,
        ["objects", "network", "create", "--name", "my-network", "--value", "10.10.0.0/24"],
    )

    assert result.exit_code != 0
    assert "Object already exists" in result.output
    assert "CONFLICT" in result.output


class TestCheck:
    """Tests for the --check flag on the create command."""

    def test_should_report_existing_object(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Check flag should report when a network object already exists."""
        called: dict[str, bool] = {"create": False}

        def fake_get_by_name(self: NetworkObjectService, name: str) -> NetworkObjectResponse:
            return SAMPLE_RESPONSE

        def fake_create(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
            called["create"] = True
            return SAMPLE_RESPONSE

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "get_network_object_by_name", fake_get_by_name)
        monkeypatch.setattr(NetworkObjectService, "create_network_object", fake_create)

        result = cli_runner.invoke(
            cli,
            ["objects", "network", "create", "--check", "--name", "my-network"],
        )

        assert result.exit_code == 0
        assert "already exists" in result.output
        assert "create would fail" in result.output
        assert not called["create"]

    def test_should_report_missing_object(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Check flag should report when a network object does not exist."""
        called: dict[str, bool] = {"create": False}

        def fake_get_by_name(self: NetworkObjectService, name: str) -> NetworkObjectResponse | None:
            return None

        def fake_create(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectResponse:
            called["create"] = True
            return SAMPLE_RESPONSE

        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
        monkeypatch.setattr(NetworkObjectService, "get_network_object_by_name", fake_get_by_name)
        monkeypatch.setattr(NetworkObjectService, "create_network_object", fake_create)

        result = cli_runner.invoke(
            cli,
            ["objects", "network", "create", "--check", "--name", "no-such-object"],
        )

        assert result.exit_code == 0
        assert "not found" in result.output
        assert "create can proceed" in result.output
        assert not called["create"]

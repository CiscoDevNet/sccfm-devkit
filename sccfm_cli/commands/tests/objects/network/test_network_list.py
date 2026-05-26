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
from sccfm_core.services import NetworkObjectService
from sccfm_core.services.object_management import (
    NetworkObjectListResponse,
    NetworkObjectResponse,
)

SAMPLE_PAGE = NetworkObjectListResponse(
    count=2,
    items=[
        NetworkObjectResponse(
            uid="abc-123",
            name="my-network",
            description="Test network",
            elements=[],
            labels=["production"],
            tags={"env": ["prod"]},
            object_type="NETWORK_OBJECT",
            literal="10.10.0.0/24",
        ),
        NetworkObjectResponse(
            uid="def-456",
            name="other-network",
            description=None,
            elements=[],
            labels=[],
            tags={},
            object_type="NETWORK_OBJECT",
            literal="192.168.1.0/24",
        ),
    ],
    limit=50,
    offset=0,
)


def _stub_init(self: NetworkObjectService, config: Any) -> None:
    return None


def test_should_list_network_objects_with_json_output(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """List command should return valid JSON when format is json."""

    def fake_list(
        self: NetworkObjectService,
        *,
        limit: int = 50,
        offset: int = 0,
        query: str | None = None,
    ) -> NetworkObjectListResponse:
        return SAMPLE_PAGE

    monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkObjectService, "list_network_objects", fake_list)

    result = cli_runner.invoke(
        cli,
        ["objects", "network", "list", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["uid"] == "abc-123"
    assert payload["items"][1]["uid"] == "def-456"


def test_should_display_table_output(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """List command should display a table by default."""

    def fake_list(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectListResponse:
        return SAMPLE_PAGE

    monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkObjectService, "list_network_objects", fake_list)

    result = cli_runner.invoke(
        cli,
        ["objects", "network", "list"],
    )

    assert result.exit_code == 0
    assert "Network Objects" in result.output
    assert "1–2 of 2" in result.output
    assert "abc-123" in result.output
    assert "my-network" in result.output
    assert "def-456" in result.output


def test_should_pass_query_and_pagination(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """List command should forward --query, --limit, --offset to the service."""
    captured: dict[str, Any] = {}

    def fake_list(
        self: NetworkObjectService,
        *,
        limit: int = 50,
        offset: int = 0,
        query: str | None = None,
    ) -> NetworkObjectListResponse:
        captured["limit"] = limit
        captured["offset"] = offset
        captured["query"] = query
        return SAMPLE_PAGE

    monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkObjectService, "list_network_objects", fake_list)

    result = cli_runner.invoke(
        cli,
        [
            "objects",
            "network",
            "list",
            "--limit",
            "10",
            "--offset",
            "5",
            "--query",
            "name:test",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["limit"] == 10
    assert captured["offset"] == 5
    assert captured["query"] == "name:test"


def test_should_display_api_error(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    """List command should display API errors."""
    error_body = json.dumps(
        {
            "errorMsg": "Unauthorized",
            "errorCode": "UNAUTHORIZED",
            "details": {},
        }
    )

    def fake_list(self: NetworkObjectService, **kwargs: Any) -> NetworkObjectListResponse:
        raise ApiException(status=401, body=error_body)

    monkeypatch.setattr(NetworkObjectService, "__init__", _stub_init)
    monkeypatch.setattr(NetworkObjectService, "list_network_objects", fake_list)

    result = cli_runner.invoke(
        cli,
        ["objects", "network", "list"],
    )

    assert result.exit_code != 0
    assert "Unauthorized" in result.output

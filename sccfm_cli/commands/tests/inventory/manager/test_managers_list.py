from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import Device, DevicePage

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services import InventoryService


def test_should_return_managers_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_managers: list[Device],
) -> None:
    captured_params: dict[str, Any] = {}
    expected_limit = 1
    expected_offset = 0
    expected_query = "edge"

    def fake_get_managers(
        self: InventoryService,
        *,
        limit: int,
        offset: int,
        query: str | None = None,
    ) -> DevicePage:
        captured_params["limit"] = limit
        captured_params["offset"] = offset
        captured_params["query"] = query
        return DevicePage(count=len(sample_managers), items=sample_managers)

    monkeypatch.setattr(InventoryService, "get_managers", fake_get_managers)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "manager",
            "list",
            "--limit",
            str(expected_limit),
            "--query",
            expected_query,
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured_params["limit"] == expected_limit
    assert captured_params["offset"] == expected_offset
    assert captured_params["query"] == expected_query

    payload = json.loads(result.output)
    assert len(payload) == 2
    expected_payload = [manager.to_dict() for manager in sample_managers]
    assert payload == expected_payload


def test_should_display_managers_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_managers: list[Device],
) -> None:
    """Managers list command should display formatted table with manager information."""

    def fake_get_managers(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(
            count=len(sample_managers),
            limit=limit,
            offset=offset,
            items=sample_managers,
        )

    monkeypatch.setattr(InventoryService, "get_managers", fake_get_managers)

    result = cli_runner.invoke(cli, ["inventory", "manager", "list", "--offset", "1"])

    assert result.exit_code == 0
    assert "Number of entries:" in result.output
    assert "Page:" in result.output
    assert "Managers" in result.output
    for sample_manager in sample_managers:
        assert sample_manager.name in result.output

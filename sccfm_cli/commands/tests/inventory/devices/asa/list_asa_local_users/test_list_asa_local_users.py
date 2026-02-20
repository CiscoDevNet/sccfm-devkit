from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import (
    CdoCliResult,
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)

from sccfm_cli.cli import cli
from sccfm_cli.commands.inventory.devices.asa.list_asa_local_users.command import (
    _normalize_output,
    _parse_cli_table,
    _rows_to_dicts,
)
from sccfm_cli.models import Config
from sccfm_core.services import AsaCommandLineService, InventoryService

# ---------------------------------------------------------------------------
# Unit tests for pure helper functions
# ---------------------------------------------------------------------------


class TestNormalizeOutput:
    def test_returns_empty_for_none(self) -> None:
        assert _normalize_output(None) == []

    def test_returns_empty_for_empty_string(self) -> None:
        assert _normalize_output("") == []

    def test_strips_blank_lines_and_whitespace(self) -> None:
        raw = "  hello  \n\n  world  \n"
        assert _normalize_output(raw) == ["  hello", "  world"]

    def test_converts_escaped_tabs(self) -> None:
        raw = "col1\\tcol2"
        result = _normalize_output(raw)
        assert result == ["col1\tcol2"]


class TestParseCliTable:
    def test_returns_empty_for_no_lines(self) -> None:
        assert _parse_cli_table([]) == ([], [])

    def test_parses_header_and_single_row(self) -> None:
        lines = [
            "User  Locked  Expired",
            "cisco  N       N",
        ]
        headers, rows = _parse_cli_table(lines)
        assert headers == ["User", "Locked", "Expired"]
        assert rows == [["cisco", "N", "N"]]

    def test_pads_short_rows(self) -> None:
        lines = ["A  B  C", "x"]
        _, rows = _parse_cli_table(lines)
        assert rows == [["x", "", ""]]

    def test_merges_extra_columns(self) -> None:
        lines = ["A  B", "x  y  z  w"]
        _, rows = _parse_cli_table(lines, max_columns=2)
        assert rows == [["x", "y z w"]]


class TestRowsToDicts:
    def test_basic_conversion(self) -> None:
        headers = ["User", "Locked"]
        rows = [["cisco", "N"], ["admin", "Y"]]
        result = _rows_to_dicts(headers, rows)
        assert result == [{"user": "cisco", "locked": "N"}, {"user": "admin", "locked": "Y"}]

    def test_normalises_header_names(self) -> None:
        headers = ["Lock-time", "Failed-attempts", "New User"]
        rows = [["10", "3", "N"]]
        result = _rows_to_dicts(headers, rows)
        assert result == [{"lock_time": "10", "failed_attempts": "3", "new_user": "N"}]


# ---------------------------------------------------------------------------
# Shared fixtures & stubs for integration tests
# ---------------------------------------------------------------------------

_SAMPLE_DEVICE = Device(
    uid="uid-1",
    name="branch-fw",
    device_type=EntityType.ASA,
    software_version="9.16.1",
    connectivity_state=ConnectivityState.ONLINE,
    config_state=ConfigState.SYNCED,
)

_SAMPLE_DEVICE_2 = Device(
    uid="uid-2",
    name="dc-fw",
    device_type=EntityType.ASA,
    software_version="9.18.2",
    connectivity_state=ConnectivityState.ONLINE,
    config_state=ConfigState.SYNCED,
)


def _stub_asa_init(self: AsaCommandLineService, config: Any) -> None:
    return None


def _stub_inventory_init(self: InventoryService, config: Any) -> None:
    return None


def _stub_get_devices(
    self: InventoryService,
    *,
    limit: int,
    offset: int,
    query: str | None,
) -> DevicePage:
    """Return SAMPLE devices whose UIDs appear in the query."""
    page = MagicMock(spec=DevicePage)
    items = []
    for dev in [_SAMPLE_DEVICE, _SAMPLE_DEVICE_2]:
        # dev.uid may be Optional[str]; guard before using `in` to satisfy type checkers
        if dev.uid and (dev.uid in (query or "")):
            items.append(dev)
    # If query-based (no uid: prefix), return all.
    if items == [] and query and "uid:" not in query:
        items = [_SAMPLE_DEVICE, _SAMPLE_DEVICE_2]
    page.items = items
    return page


# ---------------------------------------------------------------------------
# Integration tests (Click CLI runner)
# ---------------------------------------------------------------------------


def test_renders_table_with_device_name(
    cli_runner: CliRunner, default_config: Config, monkeypatch: MonkeyPatch
) -> None:
    """Command should show device name, uid, and parsed table columns."""
    sample_result = CdoCliResult(
        uid="r1",
        device_uid="uid-1",
        result=(
            "Lock-time  Failed-attempts      Locked  Expired New-User        User\n"
            "    -                   0       N       N       N               cisco"
        ),
        error_msg=None,
    )

    def fake_execute_cli(
        self: AsaCommandLineService, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        return [sample_result]

    monkeypatch.setattr(AsaCommandLineService, "__init__", _stub_asa_init)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(InventoryService, "__init__", _stub_inventory_init)
    monkeypatch.setattr(InventoryService, "get_devices", _stub_get_devices)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-local-users", "-u", "uid-1"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    output = result.output
    # Device name and uid columns
    assert "branch-fw" in output
    assert "uid-1" in output
    # Header tokens (Rich may truncate column names in narrow terminals)
    assert "Lock-time" in output
    assert "Failed-a" in output
    # Data value
    assert "cisco" in output


def test_handles_empty_result(
    cli_runner: CliRunner, default_config: Config, monkeypatch: MonkeyPatch
) -> None:
    """Command should handle empty CLI output gracefully."""
    sample_result = CdoCliResult(uid="r2", device_uid="uid-1", result="", error_msg=None)

    def fake_execute_cli(
        self: AsaCommandLineService, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        return [sample_result]

    monkeypatch.setattr(AsaCommandLineService, "__init__", _stub_asa_init)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(InventoryService, "__init__", _stub_inventory_init)
    monkeypatch.setattr(InventoryService, "get_devices", _stub_get_devices)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-local-users", "-u", "uid-1"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "no output" in result.output


def test_json_output_grouped_by_device(
    cli_runner: CliRunner, default_config: Config, monkeypatch: MonkeyPatch
) -> None:
    """JSON format should produce a dict keyed by device name."""
    sample_result = CdoCliResult(
        uid="r1",
        device_uid="uid-1",
        result="User  Locked\ncisco  N\nadmin  Y",
        error_msg=None,
    )

    def fake_execute_cli(
        self: AsaCommandLineService, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        return [sample_result]

    monkeypatch.setattr(AsaCommandLineService, "__init__", _stub_asa_init)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(InventoryService, "__init__", _stub_inventory_init)
    monkeypatch.setattr(InventoryService, "get_devices", _stub_get_devices)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-local-users", "-u", "uid-1", "--format", "json"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    data = json.loads(result.output)
    assert "branch-fw" in data
    users = data["branch-fw"]
    assert len(users) == 2
    assert users[0] == {"user": "cisco", "locked": "N"}
    assert users[1] == {"user": "admin", "locked": "Y"}


def test_multi_device_table(
    cli_runner: CliRunner, default_config: Config, monkeypatch: MonkeyPatch
) -> None:
    """Multiple device UIDs should yield rows for each device."""
    results = [
        CdoCliResult(
            uid="r1",
            device_uid="uid-1",
            result="User  Locked\ncisco  N",
            error_msg=None,
        ),
        CdoCliResult(
            uid="r2",
            device_uid="uid-2",
            result="User  Locked\nadmin  Y",
            error_msg=None,
        ),
    ]

    def fake_execute_cli(
        self: AsaCommandLineService, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        return results

    monkeypatch.setattr(AsaCommandLineService, "__init__", _stub_asa_init)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(InventoryService, "__init__", _stub_inventory_init)
    monkeypatch.setattr(InventoryService, "get_devices", _stub_get_devices)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-local-users", "-u", "uid-1", "-u", "uid-2"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    output = result.output
    assert "branch-fw" in output
    assert "dc-fw" in output
    assert "cisco" in output
    assert "admin" in output


def test_query_based_search(
    cli_runner: CliRunner, default_config: Config, monkeypatch: MonkeyPatch
) -> None:
    """Using --query should resolve devices via inventory search."""
    sample_result = CdoCliResult(
        uid="r1",
        device_uid="uid-1",
        result="User  Locked\ncisco  N",
        error_msg=None,
    )

    def fake_execute_cli(
        self: AsaCommandLineService, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        return [sample_result]

    captured_query: list[str] = []

    def capturing_get_devices(
        self: InventoryService,
        *,
        limit: int,
        offset: int,
        query: str | None,
    ) -> DevicePage:
        captured_query.append(query or "")
        page = MagicMock(spec=DevicePage)
        page.items = [_SAMPLE_DEVICE]
        return page

    monkeypatch.setattr(AsaCommandLineService, "__init__", _stub_asa_init)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(InventoryService, "__init__", _stub_inventory_init)
    monkeypatch.setattr(InventoryService, "get_devices", capturing_get_devices)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-local-users", "-q", "name:branch-*"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert len(captured_query) == 1
    assert "name:branch-*" in captured_query[0]
    assert "deviceType:ASA" in captured_query[0]
    assert "cisco" in result.output


def test_fails_when_no_filter_provided(
    cli_runner: CliRunner, default_config: Config, monkeypatch: MonkeyPatch
) -> None:
    """Command should fail when neither --query nor --device-uids is given."""
    monkeypatch.setattr(AsaCommandLineService, "__init__", _stub_asa_init)
    monkeypatch.setattr(InventoryService, "__init__", _stub_inventory_init)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-local-users"],
    )

    assert result.exit_code != 0
    assert "Provide one of" in result.output

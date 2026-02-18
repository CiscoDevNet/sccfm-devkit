from __future__ import annotations

from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import (
    CdoCliResult,
    ConfigState,
    ConnectivityState,
    Device,
    EntityType,
)

from sccfm_cli.cli import cli
from sccfm_cli.commands.inventory.devices.asa.list_local_users.command import (
    _format_device_label,
    _normalize_output,
    _parse_cli_table,
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


class TestFormatDeviceLabel:
    def test_with_name(self) -> None:
        assert _format_device_label("uid-1", "fw-01") == "fw-01 (uid-1)"

    def test_without_name(self) -> None:
        assert _format_device_label("uid-1", None) == "uid-1"

    def test_empty_name_treated_as_none(self) -> None:
        assert _format_device_label("uid-1", "") == "uid-1"


# ---------------------------------------------------------------------------
# Integration tests (Click CLI runner)
# ---------------------------------------------------------------------------

_SAMPLE_DEVICE = Device(
    uid="uid-1",
    name="branch-fw",
    device_type=EntityType.ASA,
    software_version="9.16.1",
    connectivity_state=ConnectivityState.ONLINE,
    config_state=ConfigState.SYNCED,
)


def _stub_asa_init(self: AsaCommandLineService, config: Any) -> None:
    return None


def _stub_inventory_init(self: InventoryService, config: Any) -> None:
    return None


def _stub_get_device_by_uid(self: InventoryService, device_uid: str) -> Device:
    return _SAMPLE_DEVICE


def test_renders_table_with_device_name(
    cli_runner: CliRunner, default_config: Config, monkeypatch: MonkeyPatch
) -> None:
    """Command should show device_name (device_uid) and parsed table."""
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
    monkeypatch.setattr(InventoryService, "get_device_by_uid", _stub_get_device_by_uid)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-local-users", "--uid", "uid-1"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    output = result.output
    # Device label should contain name and uid
    assert "branch-fw" in output
    assert "uid-1" in output
    # Header tokens should appear
    assert "Lock-time" in output
    assert "Failed-attempts" in output
    # Data value should appear
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
    monkeypatch.setattr(InventoryService, "get_device_by_uid", _stub_get_device_by_uid)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-local-users", "--uid", "uid-1"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "(no output)" in result.output


def test_falls_back_to_uid_when_inventory_fails(
    cli_runner: CliRunner, default_config: Config, monkeypatch: MonkeyPatch
) -> None:
    """When InventoryService raises, command should fall back to uid-only label."""
    sample_result = CdoCliResult(
        uid="r3",
        device_uid="uid-99",
        result="User  Locked\nadmin  N",
        error_msg=None,
    )

    def fake_execute_cli(
        self: AsaCommandLineService, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        return [sample_result]

    def failing_inventory_init(self: InventoryService, config: Any) -> None:
        raise ConnectionError("cannot reach API")

    monkeypatch.setattr(AsaCommandLineService, "__init__", _stub_asa_init)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(InventoryService, "__init__", failing_inventory_init)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-local-users", "--uid", "uid-99"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    # Should show uid without name
    assert "uid-99" in result.output
    assert "admin" in result.output

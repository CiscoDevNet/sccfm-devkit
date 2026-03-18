"""Tests for sccfm_cli inventory devices asa shun add command."""

from __future__ import annotations

import json
from typing import Any, List

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import CdoCliResult, Device, DevicePage

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services import InventoryService
from sccfm_core.services.inventory.asa_shun_service import AsaShunService

# ── Sample data ──────────────────────────────────────────────────


def _sample_cli_results() -> list[CdoCliResult]:
    return [
        CdoCliResult(uid="cli-1", device_uid="uid-1", result="", error_msg=None),
        CdoCliResult(uid="cli-2", device_uid="uid-2", result="", error_msg=None),
    ]


# ── Helpers ──────────────────────────────────────────────────────


def _patch_services(
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    cli_results: list[CdoCliResult] | None = None,
    captured: dict[str, Any] | None = None,
) -> None:
    """Wire up monkeypatches for InventoryService + AsaShunService."""

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        if captured is not None:
            captured["query"] = query
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_add_shun(
        self: AsaShunService,
        device_uids: List[str],
        source_ip: str,
        dest_ip: str | None = None,
        source_port: int | None = None,
        dest_port: int | None = None,
        protocol: str | None = None,
    ) -> list[CdoCliResult]:
        if captured is not None:
            captured["device_uids"] = device_uids
            captured["source_ip"] = source_ip
            captured["dest_ip"] = dest_ip
            captured["source_port"] = source_port
            captured["dest_port"] = dest_port
            captured["protocol"] = protocol
        return cli_results or _sample_cli_results()

    def stub_init(self: AsaShunService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaShunService, "add_shun", fake_add_shun)
    monkeypatch.setattr(AsaShunService, "__init__", stub_init)


# ── JSON output ──────────────────────────────────────────────────


def test_should_add_shun_with_source_ip_only(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """shun add --source-ip returns CLI results as JSON."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--source-ip",
            "10.1.1.27",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured["device_uids"] == ["uid-1", "uid-2"]
    assert captured["source_ip"] == "10.1.1.27"
    assert captured["dest_ip"] is None

    payload = json.loads(result.output)
    assert len(payload) == 2
    assert payload[0]["device_uid"] == "uid-1"


def test_should_add_shun_with_connection_tuple(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """shun add with connection-tuple params passes them to the service."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "-u",
            "uid-1",
            "--source-ip",
            "10.1.1.27",
            "--dest-ip",
            "10.2.2.89",
            "--source-port",
            "555",
            "--dest-port",
            "443",
            "--protocol",
            "tcp",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured["source_ip"] == "10.1.1.27"
    assert captured["dest_ip"] == "10.2.2.89"
    assert captured["source_port"] == 555
    assert captured["dest_port"] == 443
    assert captured["protocol"] == "tcp"


# ── Table output ─────────────────────────────────────────────────


def test_should_display_add_result_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """shun add renders table output by default."""
    _patch_services(monkeypatch, sample_devices)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "-u",
            "uid-1",
            "--source-ip",
            "10.1.1.27",
        ],
    )

    assert result.exit_code == 0
    assert "shun 10.1.1.27" in result.output


# ── Check mode ───────────────────────────────────────────────────


def test_check_mode_should_skip_service_call(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """shun add --check should resolve targets without calling the service."""
    add_called = {"called": False}

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_add_shun(
        self: AsaShunService, device_uids: list[str], source_ip: str, **kwargs: Any
    ) -> list[CdoCliResult]:
        add_called["called"] = True
        return []

    def stub_init(self: AsaShunService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaShunService, "add_shun", fake_add_shun)
    monkeypatch.setattr(AsaShunService, "__init__", stub_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "-u",
            "uid-1",
            "--source-ip",
            "10.1.1.27",
            "--check",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert add_called["called"] is False

    payload = json.loads(result.output)
    assert payload["operation"] == "shun add"
    assert payload["can_proceed"] is True


# ── Validation errors ────────────────────────────────────────────


def test_should_fail_when_connection_params_without_dest_ip(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """shun add should fail when --source-port given without --dest-ip."""
    _patch_services(monkeypatch, sample_devices)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "-u",
            "uid-1",
            "--source-ip",
            "10.1.1.27",
            "--source-port",
            "555",
        ],
    )

    assert result.exit_code != 0
    assert "--dest-ip is required" in result.output


def test_should_fail_without_any_filter(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    """shun add fails when no device selector is provided."""
    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "shun", "add", "--source-ip", "10.1.1.27"],
    )

    assert result.exit_code != 0
    assert "Provide one of" in result.output


def test_should_filter_devices_by_query(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """shun add passes --query with ASA type appended."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "--query",
            "name:branch-*",
            "--source-ip",
            "10.1.1.27",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured["query"] == "name:branch-* AND deviceType:ASA"

from __future__ import annotations

import json
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import ConfigState, ConnectivityState, Device, DevicePage, EntityType

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_cli.services import ConfigService
from sccfm_core.services import InventoryService


def test_inventory_devices_command_json(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("SCCFM_CONFIG", str(config_path))
    ConfigService(path=config_path).save(
        Config(profile="default", region="us", api_token="tok12345")
    )

    calls: dict[str, tuple[str, int, int, str]] = {}

    def stub_init(self: InventoryService, config: Config) -> None:
        return None

    monkeypatch.setattr(InventoryService, "__init__", stub_init)

    def fake_get_devices(
        self: InventoryService,
        *,
        config: Config,
        limit: int,
        offset: int,
        query: str | None = None,
    ) -> DevicePage:
        calls["devices"] = (config.profile, limit, offset, query or "")
        items = [
            Device(
                uid="uid-1",
                name="perimeter-fw",
                device_type=EntityType.GENERIC_DEVICE,
                software_version="1.0.0",
                connectivity_state=ConnectivityState.ONLINE,
                config_state=ConfigState.SYNCED,
            ),
            Device(
                uid="uid-2",
                name="edge-nva",
                device_type=EntityType.GENERIC_DEVICE,
                software_version="1.0.0",
                connectivity_state=ConnectivityState.ONLINE,
                config_state=ConfigState.SYNCED,
            ),
        ]
        return DevicePage(count=len(items), items=items)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "list",
            "--limit",
            "1",
            "--query",
            "edge",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload[0]["name"] == "perimeter-fw"
    assert calls["devices"] == ("default", 1, 0, "edge")


def test_inventory_managers_table(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("SCCFM_CONFIG", str(config_path))
    ConfigService(path=config_path).save(
        Config(profile="default", region="us", api_token="tok12345")
    )

    calls: dict[str, tuple[str, int, int, str]] = {}

    def stub_init(self: InventoryService, config: Config) -> None:
        return None

    monkeypatch.setattr(InventoryService, "__init__", stub_init)

    def fake_get_managers(
        self: InventoryService,
        *,
        config: Config,
        limit: int,
        offset: int,
        query: str | None = None,
    ) -> DevicePage:
        calls["managers"] = (config.profile, limit, offset, query or "")
        items = [
            Device(
                uid="uid-1",
                name="us-east-manager",
                device_type=EntityType.ONPREM_FMC,
                software_version="3.0.0",
                connectivity_state=ConnectivityState.ONLINE,
                config_state=ConfigState.SYNCED,
            ),
            Device(
                uid="uid-2",
                name="eu-central-manager",
                device_type=EntityType.ONPREM_FMC,
                software_version="3.0.0",
                connectivity_state=ConnectivityState.ONLINE,
                config_state=ConfigState.SYNCED,
            ),
        ]
        return DevicePage(count=len(items), items=items)

    monkeypatch.setattr(InventoryService, "get_managers", fake_get_managers)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "inventory",
            "managers",
            "list",
            "--offset",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert "Managers" in result.output
    assert "eu-central-manager" in result.output
    assert calls["managers"] == ("default", 50, 1, "")


def test_configure_command_creates_profile(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("SCCFM_CONFIG", str(config_path))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--profile",
            "lab",
            "configure",
            "--region",
            "eu",
            "--api-token",
            "token-xyz",
            "--config-path",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Profile 'lab' updated" in result.output

    service = ConfigService(path=config_path)
    stored = service.load("lab")
    assert stored is not None
    assert stored.region == "eu"
    assert stored.api_token == "token-xyz"

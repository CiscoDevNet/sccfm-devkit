"""Tests for sccfm_cli.commands.base — filter_online_devices."""

from __future__ import annotations

from typing import Any, Sequence

import click
import pytest
from rich.console import Console
from scc_firewall_manager_sdk import (
    ConfigState,
    ConnectivityState,
    Device,
    EntityType,
)

from sccfm_cli.commands.base import BaseCommand


# ── Concrete stub so we can instantiate BaseCommand ──────────────


class _StubCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "stub"

    def build_params(self) -> Sequence[click.Parameter]:
        return []

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        pass


# ── Helpers ──────────────────────────────────────────────────────


def _device(
    uid: str,
    name: str,
    state: ConnectivityState = ConnectivityState.ONLINE,
) -> Device:
    return Device(
        uid=uid,
        name=name,
        device_type=EntityType.ASA,
        software_version="9.18(2)",
        connectivity_state=state,
        config_state=ConfigState.SYNCED,
    )


# ── Tests ────────────────────────────────────────────────────────


class TestFilterOnlineDevices:
    """Tests for BaseCommand.filter_online_devices()."""

    def _make_command(self) -> _StubCommand:
        return _StubCommand(console=Console(stderr=True))

    def test_returns_only_online_devices(self) -> None:
        cmd = self._make_command()
        devices = [
            _device("uid-1", "asa-online", ConnectivityState.ONLINE),
            _device("uid-2", "asa-offline", ConnectivityState.UNREACHABLE),
        ]
        result = cmd.filter_online_devices(devices)
        assert len(result) == 1
        assert result[0].uid == "uid-1"

    def test_all_devices_online(self) -> None:
        cmd = self._make_command()
        devices = [
            _device("uid-1", "asa-1", ConnectivityState.ONLINE),
            _device("uid-2", "asa-2", ConnectivityState.ONLINE),
        ]
        result = cmd.filter_online_devices(devices)
        assert len(result) == 2

    def test_raises_when_no_devices_online(self) -> None:
        cmd = self._make_command()
        devices = [
            _device("uid-1", "asa-down", ConnectivityState.UNREACHABLE),
            _device("uid-2", "asa-pending", ConnectivityState.PENDING),
        ]
        with pytest.raises(click.ClickException, match="No online devices found"):
            cmd.filter_online_devices(devices)

    def test_filters_all_non_online_states(self) -> None:
        cmd = self._make_command()
        devices = [
            _device("uid-1", "online", ConnectivityState.ONLINE),
            _device("uid-2", "unreachable", ConnectivityState.UNREACHABLE),
            _device("uid-3", "bad-creds", ConnectivityState.BAD_CREDENTIALS),
            _device("uid-4", "unknown", ConnectivityState.UNKNOWN),
            _device("uid-5", "pending-setup", ConnectivityState.PENDING_SETUP),
            _device("uid-6", "pending", ConnectivityState.PENDING),
            _device("uid-7", "new-cert", ConnectivityState.NEW_CERT_DETECTED),
        ]
        result = cmd.filter_online_devices(devices)
        assert len(result) == 1
        assert result[0].name == "online"

    def test_empty_device_list_raises(self) -> None:
        cmd = self._make_command()
        with pytest.raises(click.ClickException, match="No online devices found"):
            cmd.filter_online_devices([])

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for sccfm_cli inventory devices asa list-not-on-version command."""

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import ConfigState, ConnectivityState, Device, DevicePage, EntityType

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services import InventoryService

_TARGET_VERSION = "9.20(3)13"


def _sample_devices() -> list[Device]:
    return [
        Device(
            uid="uid-1",
            name="perimeter-fw",
            device_type=EntityType.ASA,
            software_version="9.18.4",
            asdm_version="7.18(1)",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
        Device(
            uid="uid-2",
            name="edge-asa",
            device_type=EntityType.ASA,
            software_version="9.16.3",
            asdm_version="7.16(1)",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
    ]


def _patch_inventory(
    monkeypatch: MonkeyPatch,
    devices: list[Device],
    captured: dict[str, Any] | None = None,
) -> None:
    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        if captured is not None:
            captured["query"] = query
            captured["limit"] = limit
            captured["offset"] = offset
        return DevicePage(count=len(devices), items=devices)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)


# ── JSON output ───────────────────────────────────────────────────


def test_returns_devices_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Returns JSON with metadata and expected device fields."""
    _patch_inventory(monkeypatch, _sample_devices())

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-not-on-version",
            "--version",
            _TARGET_VERSION,
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    payload = json.loads(result.output)
    assert payload["version"] == _TARGET_VERSION
    assert payload["matched_device_count"] == 2
    assert payload["device_count"] == 2
    assert len(payload["devices"]) == 2

    first = payload["devices"][0]
    assert first["uid"] == "uid-1"
    assert first["name"] == "perimeter-fw"
    assert first["software_version"] == "9.18.4"
    assert first["asdm_version"] == "7.18(1)"
    assert first["connectivity_state"] is not None


# ── Table output ──────────────────────────────────────────────────


def test_returns_devices_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Renders a table containing device names and version info."""
    _patch_inventory(monkeypatch, _sample_devices())

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-not-on-version", "--version", _TARGET_VERSION],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    # Rich may truncate cell values in narrow terminals; check partial prefixes
    assert "perimeter-" in result.output
    assert "edge-asa" in result.output
    assert "9.18.4" in result.output


# ── Query construction ────────────────────────────────────────────


def test_query_filters_by_asa_device_type(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Query sent to inventory contains deviceType:ASA."""
    captured: dict[str, Any] = {}
    _patch_inventory(monkeypatch, [], captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-not-on-version",
            "--version",
            _TARGET_VERSION,
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "deviceType:ASA" in captured["query"]


def test_client_side_filters_out_matching_version(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Devices on the target version are excluded from the JSON output."""
    devices_with_target = [
        *_sample_devices(),
        Device(
            uid="uid-3",
            name="up-to-date-asa",
            device_type=EntityType.ASA,
            software_version=_TARGET_VERSION,
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
    ]
    _patch_inventory(monkeypatch, devices_with_target)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-not-on-version",
            "--version",
            _TARGET_VERSION,
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    payload = json.loads(result.output)
    assert payload["matched_device_count"] == 3
    assert payload["device_count"] == 2
    # uid-3 is on the target version and must be excluded
    uids = [d["uid"] for d in payload["devices"]]
    assert "uid-3" not in uids
    assert "uid-1" in uids
    assert "uid-2" in uids


def test_combines_device_name_with_asa_type_filter(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """--device-name is combined with deviceType:ASA in the query."""
    captured: dict[str, Any] = {}
    _patch_inventory(monkeypatch, [], captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-not-on-version",
            "--version",
            _TARGET_VERSION,
            "--device-name",
            "branch-*",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "name:branch-*" in captured["query"]
    assert "deviceType:ASA" in captured["query"]


def test_combines_user_query_with_asa_type_filter(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """--query is wrapped and combined with deviceType:ASA filter."""
    captured: dict[str, Any] = {}
    _patch_inventory(monkeypatch, [], captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-not-on-version",
            "--version",
            _TARGET_VERSION,
            "--query",
            "name:edge-*",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "(name:edge-*)" in captured["query"]
    assert "deviceType:ASA" in captured["query"]


# ── Pagination ────────────────────────────────────────────────────


def test_passes_limit_and_offset(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """--limit and --offset are forwarded to the inventory service."""
    captured: dict[str, Any] = {}
    _patch_inventory(monkeypatch, [], captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-not-on-version",
            "--version",
            _TARGET_VERSION,
            "--limit",
            "25",
            "--offset",
            "10",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured["limit"] == 25
    assert captured["offset"] == 10


# ── Empty results ─────────────────────────────────────────────────


def test_handles_empty_results(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """No matching devices should be reported distinctly from compliant devices."""
    _patch_inventory(monkeypatch, [])

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-not-on-version",
            "--version",
            _TARGET_VERSION,
            "--query",
            "name:missing-*",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "No ASA devices matched the given filter." in result.output


def test_handles_empty_results_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """JSON output should distinguish no matches from compliant matches."""
    _patch_inventory(monkeypatch, [])

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-not-on-version",
            "--version",
            _TARGET_VERSION,
            "--query",
            "name:missing-*",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert json.loads(result.output) == {
        "version": _TARGET_VERSION,
        "matched_device_count": 0,
        "device_count": 0,
        "devices": [],
    }


def test_all_compliant_devices_are_reported_distinctly(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Matched compliant devices should not be confused with a zero-match filter result."""
    all_on_target = [
        Device(
            uid="uid-1",
            name="up-to-date-asa",
            device_type=EntityType.ASA,
            software_version=_TARGET_VERSION,
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
    ]
    _patch_inventory(monkeypatch, all_on_target)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-not-on-version", "--version", _TARGET_VERSION],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "All 1 matched device(s) are on version" in result.output


# ── Idempotency ───────────────────────────────────────────────────


def test_idempotent_repeated_invocations_return_same_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Running the command twice with the same data produces identical JSON output."""
    _patch_inventory(monkeypatch, _sample_devices())

    results = []
    for _ in range(2):
        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "asa",
                "list-not-on-version",
                "--version",
                _TARGET_VERSION,
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, f"Command failed: {result.output}"
        results.append(json.loads(result.output))

    assert results[0] == results[1]


def test_idempotent_all_on_version_stays_empty(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """When all devices match, repeated runs still report a compliant match set."""
    all_on_target = [
        Device(
            uid="uid-1",
            name="up-to-date-asa",
            device_type=EntityType.ASA,
            software_version=_TARGET_VERSION,
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
    ]
    _patch_inventory(monkeypatch, all_on_target)

    for _ in range(2):
        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "asa",
                "list-not-on-version",
                "--version",
                _TARGET_VERSION,
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert json.loads(result.output) == {
            "version": _TARGET_VERSION,
            "matched_device_count": 1,
            "device_count": 0,
            "devices": [],
        }


# ── Validation errors ─────────────────────────────────────────────


def test_rejects_invalid_version_format(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    """A version string that doesn't match the Cisco format is rejected."""
    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-not-on-version", "--version", "not-a-version"],
    )

    assert result.exit_code != 0
    assert "Invalid version format" in result.output


def test_rejects_both_device_name_and_query(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Providing both --device-name and --query at the same time is rejected."""
    _patch_inventory(monkeypatch, [])

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-not-on-version",
            "--version",
            _TARGET_VERSION,
            "--device-name",
            "branch-*",
            "--query",
            "name:edge-*",
        ],
    )

    assert result.exit_code != 0
    assert "Provide only one of" in result.output


def test_accepts_device_uids_selector(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """The command should expose the shared ASA UID selector surface."""
    captured: dict[str, Any] = {}
    _patch_inventory(monkeypatch, _sample_devices(), captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-not-on-version",
            "--version",
            _TARGET_VERSION,
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured["query"] == "uid:uid-1 OR uid:uid-2"


def test_missing_version_flag(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    """Omitting --version results in a Click error."""
    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-not-on-version"],
    )

    assert result.exit_code != 0

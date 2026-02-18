from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import CdoTransaction, Device, DevicePage

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.models.asa_password_change_result import AsaPasswordChangeResult
from sccfm_core.services import InventoryService
from sccfm_core.services.inventory.asa_user_password_service import (
    AsaUserPasswordService,
)


def _sample_results() -> dict[str, AsaPasswordChangeResult]:
    return {
        "uid-1": AsaPasswordChangeResult(
            device_uid="uid-1",
            status="success",
            message="Password changed successfully.",
        ),
        "uid-2": AsaPasswordChangeResult(
            device_uid="uid-2",
            status="success",
            message="Password changed successfully.",
        ),
    }


def _stub_password_service(monkeypatch: MonkeyPatch) -> None:
    """Stub out AsaUserPasswordService.__init__ to avoid API calls."""

    def stub_init(self: AsaUserPasswordService, config: Any) -> None:
        return None

    monkeypatch.setattr(AsaUserPasswordService, "__init__", stub_init)


def test_should_return_results_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """change-password should return valid JSON when format is json."""
    captured_params: dict[str, Any] = {}
    results = _sample_results()

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_change_password(
        self: AsaUserPasswordService,
        *,
        device_uids: list[str],
        username: str,
        new_password: str,
    ) -> dict[str, AsaPasswordChangeResult]:
        captured_params["device_uids"] = device_uids
        captured_params["username"] = username
        captured_params["new_password"] = new_password
        return results

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaUserPasswordService, "change_password", fake_change_password)
    _stub_password_service(monkeypatch)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "user",
            "change-password",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--username",
            "admin",
            "--password",
            "newpass123",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured_params["device_uids"] == ["uid-1", "uid-2"]
    assert captured_params["username"] == "admin"
    assert captured_params["new_password"] == "newpass123"

    payload = json.loads(result.output)
    assert len(payload) == 2
    assert payload[0]["device_uid"] == "uid-1"
    assert payload[0]["status"] == "success"
    assert payload[1]["device_uid"] == "uid-2"
    assert payload[1]["status"] == "success"


def test_should_display_results_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """change-password should display a formatted table by default."""
    results = _sample_results()

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_change_password(
        self: AsaUserPasswordService,
        *,
        device_uids: list[str],
        username: str,
        new_password: str,
    ) -> dict[str, AsaPasswordChangeResult]:
        return results

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaUserPasswordService, "change_password", fake_change_password)
    _stub_password_service(monkeypatch)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "user",
            "change-password",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--username",
            "admin",
            "--password",
            "newpass123",
        ],
    )

    assert result.exit_code == 0
    output = str(result.output)
    assert "uid-1" in output
    assert "uid-2" in output
    assert "success" in output
    assert "Device Name" in output
    assert "Status" in output
    assert "Message" in output


def test_should_filter_devices_by_query(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """change-password should pass query filter with ASA device type."""
    captured_params: dict[str, Any] = {}
    user_query = "name:branch-*"

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured_params["query"] = query
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_change_password(
        self: AsaUserPasswordService,
        *,
        device_uids: list[str],
        username: str,
        new_password: str,
    ) -> dict[str, AsaPasswordChangeResult]:
        return {}

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaUserPasswordService, "change_password", fake_change_password)
    _stub_password_service(monkeypatch)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "user",
            "change-password",
            "--query",
            user_query,
            "--username",
            "admin",
            "--password",
            "newpass123",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured_params["query"] == f"{user_query} AND deviceType:ASA"


def test_should_fail_without_device_filter(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    """change-password should fail when no device filter is provided."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "user",
            "change-password",
            "--username",
            "admin",
            "--password",
            "newpass123",
        ],
    )

    assert result.exit_code != 0
    assert "Provide one of" in result.output


def test_should_fail_with_multiple_device_filters(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    """change-password should fail when multiple device filters are provided."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "user",
            "change-password",
            "--query",
            "name:foo",
            "-u",
            "uid-1",
            "--username",
            "admin",
            "--password",
            "newpass123",
        ],
    )

    assert result.exit_code != 0
    assert "Provide only one of" in result.output


def test_should_fail_without_username(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    """change-password should fail when --username is not provided."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "user",
            "change-password",
            "-u",
            "uid-1",
            "--password",
            "newpass123",
        ],
    )

    assert result.exit_code != 0
    assert "username" in result.output.lower()


def test_should_render_failed_transaction_as_json_when_requested(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """change-password should render failed transaction details in JSON format."""

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_change_password(
        self: AsaUserPasswordService,
        *,
        device_uids: list[str],
        username: str,
        new_password: str,
    ) -> CdoTransaction:
        return CdoTransaction(
            transactionUid="tx-123",
            cdoTransactionStatus="ERROR",
            errorMessage="Device unreachable",
        )

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaUserPasswordService, "change_password", fake_change_password)
    _stub_password_service(monkeypatch)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "user",
            "change-password",
            "-u",
            "uid-1",
            "--username",
            "admin",
            "--password",
            "newpass123",
            "--format",
            "json",
        ],
    )

    assert result.exit_code != 0
    assert '"transactionUid": "tx-123"' in result.output
    assert '"cdoTransactionStatus": "ERROR"' in result.output

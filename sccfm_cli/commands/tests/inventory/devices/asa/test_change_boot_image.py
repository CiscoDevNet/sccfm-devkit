from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import (
    CdoTransaction,
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.models.asa_boot_image_change_result import AsaBootImageChangeResult
from sccfm_core.services import AsaBootImageService, InventoryService

UID_1 = "11111111-1111-4111-8111-111111111111"
UID_2 = "22222222-2222-4222-8222-222222222222"
IMAGE_PATH = "disk0:/asa9-18-4-smp-k8.bin"


def _ready_device(uid: str, name: str) -> Device:
    return Device(
        uid=uid,
        name=name,
        device_type=EntityType.ASA,
        connectivity_state=ConnectivityState.ONLINE,
        config_state=ConfigState.SYNCED,
    )


def _not_ready_device(uid: str, name: str) -> Device:
    return Device(
        uid=uid,
        name=name,
        device_type=EntityType.ASA,
        connectivity_state=ConnectivityState.UNREACHABLE,
        config_state=ConfigState.NOT_SYNCED,
    )


def _stub_boot_image_service(monkeypatch: MonkeyPatch) -> None:
    def stub_init(self: AsaBootImageService, config: Any) -> None:
        return None

    monkeypatch.setattr(AsaBootImageService, "__init__", stub_init)


def test_should_return_change_boot_image_results_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    devices = [_ready_device(UID_1, "asa-1"), _ready_device(UID_2, "asa-2")]

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(devices), items=devices)

    def fake_change_boot_image(
        self: AsaBootImageService, *, device_uids: list[str], image_path: str
    ) -> dict[str, AsaBootImageChangeResult]:
        captured["device_uids"] = device_uids
        captured["image_path"] = image_path
        return {
            UID_1: AsaBootImageChangeResult(
                device_uid=UID_1,
                requested_image_path=image_path,
                status="success",
                message="Boot image changed successfully.",
                boot_system_entries_before=["disk0:/old.bin"],
                boot_system_entries_after=[image_path],
            ),
            UID_2: AsaBootImageChangeResult(
                device_uid=UID_2,
                requested_image_path=image_path,
                status="no_change",
                message="Requested image is already the sole configured boot image.",
                boot_system_entries_before=[image_path],
                boot_system_entries_after=[image_path],
            ),
        }

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaBootImageService, "change_boot_image", fake_change_boot_image)
    _stub_boot_image_service(monkeypatch)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "change-boot-image",
            "-u",
            UID_1,
            "-u",
            UID_2,
            "--image-path",
            IMAGE_PATH,
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured["device_uids"] == [UID_1, UID_2]
    assert captured["image_path"] == IMAGE_PATH

    payload = json.loads(result.output)
    assert len(payload) == 2
    assert payload[0]["device_name"] == "asa-1"
    assert payload[0]["status"] == "success"
    assert payload[1]["status"] == "no_change"


def test_should_display_change_boot_image_results_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    devices = [_ready_device(UID_1, "asa-1")]

    monkeypatch.setattr(
        InventoryService,
        "get_devices",
        lambda self, *, limit, offset, query=None: DevicePage(count=1, items=devices),
    )
    monkeypatch.setattr(
        AsaBootImageService,
        "change_boot_image",
        lambda self, *, device_uids, image_path: {
            UID_1: AsaBootImageChangeResult(
                device_uid=UID_1,
                requested_image_path=image_path,
                status="success",
                message="Boot image changed successfully.",
                boot_system_entries_before=["disk0:/old.bin"],
                boot_system_entries_after=[image_path],
            )
        },
    )
    _stub_boot_image_service(monkeypatch)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "change-boot-image",
            "-u",
            UID_1,
            "--image-path",
            IMAGE_PATH,
        ],
    )

    assert result.exit_code == 0
    output = result.output
    assert "Device" in output
    assert "Requested" in output
    assert "Before" in output or "Boot Entries" in output
    assert "asa-1" in output
    assert "success" in output


def test_should_pass_query_filter_with_asa_device_type(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    devices = [_ready_device(UID_1, "asa-1")]

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured["query"] = query
        captured["limit"] = limit
        captured["offset"] = offset
        return DevicePage(count=1, items=devices)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(
        AsaBootImageService,
        "change_boot_image",
        lambda self, *, device_uids, image_path: {
            UID_1: AsaBootImageChangeResult(
                device_uid=UID_1,
                requested_image_path=image_path,
                status="success",
                message="Boot image changed successfully.",
                boot_system_entries_before=[],
                boot_system_entries_after=[image_path],
            )
        },
    )
    _stub_boot_image_service(monkeypatch)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "change-boot-image",
            "--query",
            "name:branch-*",
            "--limit",
            "10",
            "--offset",
            "5",
            "--image-path",
            IMAGE_PATH,
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["query"] == "name:branch-* AND deviceType:ASA"
    assert captured["limit"] == 10
    assert captured["offset"] == 5


def test_check_mode_should_return_predictive_results_and_skip_mutation(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    change_called = {"called": False}
    devices = [_ready_device(UID_1, "asa-1")]

    monkeypatch.setattr(
        InventoryService,
        "get_devices",
        lambda self, *, limit, offset, query=None: DevicePage(count=1, items=devices),
    )

    def fake_check_boot_image(
        self: AsaBootImageService, *, device_uids: list[str], image_path: str
    ) -> dict[str, AsaBootImageChangeResult]:
        captured["device_uids"] = device_uids
        return {
            UID_1: AsaBootImageChangeResult(
                device_uid=UID_1,
                requested_image_path=image_path,
                status="would_change",
                message="Boot image would be changed to the requested image.",
                boot_system_entries_before=["disk0:/old.bin"],
                boot_system_entries_after=[image_path],
            )
        }

    def fake_change_boot_image(
        self: AsaBootImageService, *, device_uids: list[str], image_path: str
    ) -> dict[str, AsaBootImageChangeResult]:
        change_called["called"] = True
        return {}

    monkeypatch.setattr(AsaBootImageService, "check_boot_image", fake_check_boot_image)
    monkeypatch.setattr(AsaBootImageService, "change_boot_image", fake_change_boot_image)
    _stub_boot_image_service(monkeypatch)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "change-boot-image",
            "-u",
            UID_1,
            "--image-path",
            IMAGE_PATH,
            "--check",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured["device_uids"] == [UID_1]
    assert change_called["called"] is False

    payload = json.loads(result.output)
    assert payload[0]["status"] == "would_change"


def test_should_merge_device_not_ready_results(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    devices = [_ready_device(UID_1, "asa-ready"), _not_ready_device(UID_2, "asa-staging")]

    monkeypatch.setattr(
        InventoryService,
        "get_devices",
        lambda self, *, limit, offset, query=None: DevicePage(count=2, items=devices),
    )
    monkeypatch.setattr(
        AsaBootImageService,
        "change_boot_image",
        lambda self, *, device_uids, image_path: {
            UID_1: AsaBootImageChangeResult(
                device_uid=UID_1,
                requested_image_path=image_path,
                status="success",
                message="Boot image changed successfully.",
                boot_system_entries_before=["disk0:/old.bin"],
                boot_system_entries_after=[image_path],
            )
        },
    )
    _stub_boot_image_service(monkeypatch)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "change-boot-image",
            "-u",
            UID_1,
            "-u",
            UID_2,
            "--image-path",
            IMAGE_PATH,
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    payload = json.loads(result.output)
    assert payload[0]["status"] == "success"
    assert payload[1]["status"] == "device_not_ready"
    assert "connectivity_state=UNREACHABLE" in payload[1]["message"]


def test_should_return_zero_when_all_devices_are_not_ready(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    devices = [_not_ready_device(UID_1, "asa-staging")]
    service_called = {"called": False}

    monkeypatch.setattr(
        InventoryService,
        "get_devices",
        lambda self, *, limit, offset, query=None: DevicePage(count=1, items=devices),
    )

    def fake_change_boot_image(
        self: AsaBootImageService, *, device_uids: list[str], image_path: str
    ) -> dict[str, AsaBootImageChangeResult]:
        service_called["called"] = True
        return {}

    monkeypatch.setattr(AsaBootImageService, "change_boot_image", fake_change_boot_image)
    _stub_boot_image_service(monkeypatch)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "change-boot-image",
            "-u",
            UID_1,
            "--image-path",
            IMAGE_PATH,
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert service_called["called"] is False
    payload = json.loads(result.output)
    assert payload[0]["status"] == "device_not_ready"


def test_should_fail_for_invalid_image_path(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "change-boot-image",
            "-u",
            UID_1,
            "--image-path",
            "asa9-18-4-smp-k8.bin",
        ],
    )

    assert result.exit_code != 0
    assert "full device path" in result.output


def test_should_render_failed_transaction_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    devices = [_ready_device(UID_1, "asa-1")]

    monkeypatch.setattr(
        InventoryService,
        "get_devices",
        lambda self, *, limit, offset, query=None: DevicePage(count=1, items=devices),
    )
    monkeypatch.setattr(
        AsaBootImageService,
        "change_boot_image",
        lambda self, *, device_uids, image_path: CdoTransaction(
            transactionUid="tx-123",
            cdoTransactionStatus="ERROR",
            errorMessage="Boot config update failed",
        ),
    )
    _stub_boot_image_service(monkeypatch)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "change-boot-image",
            "-u",
            UID_1,
            "--image-path",
            IMAGE_PATH,
            "--format",
            "json",
        ],
    )

    assert result.exit_code != 0
    assert '"transactionUid": "tx-123"' in result.output

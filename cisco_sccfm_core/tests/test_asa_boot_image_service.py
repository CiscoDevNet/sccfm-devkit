# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for cisco_sccfm_core.services.inventory.asa_boot_image_service."""

from __future__ import annotations

from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction

from cisco_sccfm_core.models.asa_boot_registry import AsaBootRegistry
from cisco_sccfm_core.services.inventory.asa_boot_image_service import AsaBootImageService
from cisco_sccfm_core.services.inventory.asa_boot_registry_service import AsaBootRegistryService
from cisco_sccfm_core.services.inventory.asa_cli_service import AsaCommandLineService
from cisco_sccfm_core.utils.validation import validate_asa_image_path

UID_1 = "11111111-1111-4111-8111-111111111111"
UID_2 = "22222222-2222-4222-8222-222222222222"
IMAGE_PATH = "disk0:/asa9-18-4-smp-k8.bin"
OLD_IMAGE = "disk0:/asa9-16-4-smp-k8.bin"
OLDER_IMAGE = "disk0:/asa9-14-3-11-smp-k8.bin"
IMAGE_DIR = "disk0:/"
DIR_IMAGE_OUTPUT = "Directory of disk0:/asa9-18-4-smp-k8.bin"
DIR_DIRECTORY_OUTPUT = (
    "Directory of disk0:/\n"
    "26  -rw-  123456789  Mar 18 2026  12:00:00  asa9-18-4-smp-k8.bin\n"
    "255426560 bytes total (120512512 bytes free)"
)


def _boot(entries: list[str]) -> AsaBootRegistry:
    return AsaBootRegistry(
        system_image_file=entries[0] if entries else "unknown",
        compiled_date="unknown",
        config_register="0x1",
        config_modified=False,
        boot_system_entries=entries,
    )


def _stub_service_init(monkeypatch: MonkeyPatch) -> None:
    def stub_cli_init(self: AsaCommandLineService, config: Any) -> None:
        return None

    def stub_boot_init(self: AsaBootRegistryService, config: Any) -> None:
        return None

    monkeypatch.setattr(AsaCommandLineService, "__init__", stub_cli_init)
    monkeypatch.setattr(AsaBootRegistryService, "__init__", stub_boot_init)


def test_validate_asa_image_path_accepts_full_device_paths() -> None:
    validate_asa_image_path("disk0:/asa9-18-4-smp-k8.bin")
    validate_asa_image_path("boot:/images/cisco-asa-fp1k.9.20.2.10.SPA")


def test_validate_asa_image_path_rejects_bare_filenames() -> None:
    with pytest.raises(ValueError, match="full device path"):
        validate_asa_image_path("asa9-18-4-smp-k8.bin")


def test_check_boot_image_should_return_no_change(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_service_init(monkeypatch)

    def fake_list_boot_registry(
        self: AsaBootRegistryService, device_uids: list[str]
    ) -> dict[str, AsaBootRegistry]:
        assert device_uids == [UID_1]
        return {UID_1: _boot([IMAGE_PATH])}

    def fake_execute_cli(
        self: AsaCommandLineService, *, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        assert device_uids == [UID_1]
        if asa_commands == [f"dir {IMAGE_PATH}"]:
            return [CdoCliResult(uid="r1", device_uid=UID_1, result=DIR_IMAGE_OUTPUT)]
        assert asa_commands == [f"dir {IMAGE_DIR}"]
        return [CdoCliResult(uid="r2", device_uid=UID_1, result=DIR_DIRECTORY_OUTPUT)]

    monkeypatch.setattr(AsaBootRegistryService, "list_boot_registry", fake_list_boot_registry)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)

    service = AsaBootImageService(config=object())
    results = service.check_boot_image(device_uids=[UID_1], image_path=IMAGE_PATH)

    assert not isinstance(results, CdoTransaction)
    assert results[UID_1].status == "no_change"
    assert results[UID_1].boot_system_entries_before == [IMAGE_PATH]
    assert results[UID_1].boot_system_entries_after == [IMAGE_PATH]
    assert "120512512 bytes free" in results[UID_1].message


def test_check_boot_image_should_return_would_change(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_service_init(monkeypatch)

    monkeypatch.setattr(
        AsaBootRegistryService,
        "list_boot_registry",
        lambda self, device_uids: {UID_1: _boot([OLD_IMAGE, OLDER_IMAGE])},
    )
    monkeypatch.setattr(
        AsaCommandLineService,
        "execute_cli",
        lambda self, *, device_uids, asa_commands: (
            [CdoCliResult(uid="r1", device_uid=UID_1, result=DIR_IMAGE_OUTPUT)]
            if asa_commands == [f"dir {IMAGE_PATH}"]
            else [CdoCliResult(uid="r2", device_uid=UID_1, result=DIR_DIRECTORY_OUTPUT)]
        ),
    )

    service = AsaBootImageService(config=object())
    results = service.check_boot_image(device_uids=[UID_1], image_path=IMAGE_PATH)

    assert not isinstance(results, CdoTransaction)
    assert results[UID_1].status == "would_change"
    assert results[UID_1].boot_system_entries_before == [OLD_IMAGE, OLDER_IMAGE]
    assert results[UID_1].boot_system_entries_after == [IMAGE_PATH, OLD_IMAGE]
    assert "Containing directory 'disk0:/' reports 120512512 bytes free" in results[UID_1].message


def test_check_boot_image_should_return_image_not_found(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_service_init(monkeypatch)

    monkeypatch.setattr(
        AsaBootRegistryService,
        "list_boot_registry",
        lambda self, device_uids: {UID_1: _boot([OLD_IMAGE])},
    )
    monkeypatch.setattr(
        AsaCommandLineService,
        "execute_cli",
        lambda self, *, device_uids, asa_commands: (
            [
                CdoCliResult(
                    uid="r1",
                    device_uid=UID_1,
                    result=f"Error opening {IMAGE_PATH} (No such file or directory)",
                )
            ]
            if asa_commands == [f"dir {IMAGE_PATH}"]
            else [CdoCliResult(uid="r2", device_uid=UID_1, result=DIR_DIRECTORY_OUTPUT)]
        ),
    )

    service = AsaBootImageService(config=object())
    results = service.check_boot_image(device_uids=[UID_1], image_path=IMAGE_PATH)

    assert not isinstance(results, CdoTransaction)
    assert results[UID_1].status == "image_not_found"
    assert "120512512 bytes free" in results[UID_1].message


def test_check_boot_image_should_return_failed_for_cli_error_msg(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_service_init(monkeypatch)

    monkeypatch.setattr(
        AsaBootRegistryService,
        "list_boot_registry",
        lambda self, device_uids: {UID_1: _boot([OLD_IMAGE])},
    )
    monkeypatch.setattr(
        AsaCommandLineService,
        "execute_cli",
        lambda self, *, device_uids, asa_commands: (
            [CdoCliResult(uid="r1", device_uid=UID_1, result="", error_msg="Request timed out")]
            if asa_commands == [f"dir {IMAGE_PATH}"]
            else [CdoCliResult(uid="r2", device_uid=UID_1, result=DIR_DIRECTORY_OUTPUT)]
        ),
    )

    service = AsaBootImageService(config=object())
    results = service.check_boot_image(device_uids=[UID_1], image_path=IMAGE_PATH)

    assert not isinstance(results, CdoTransaction)
    assert results[UID_1].status == "failed"
    assert "Request timed out" in results[UID_1].message


def test_check_boot_image_should_return_failed_for_filesystem_inspection_error(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_service_init(monkeypatch)

    monkeypatch.setattr(
        AsaBootRegistryService,
        "list_boot_registry",
        lambda self, device_uids: {UID_1: _boot([OLD_IMAGE])},
    )
    monkeypatch.setattr(
        AsaCommandLineService,
        "execute_cli",
        lambda self, *, device_uids, asa_commands: (
            [CdoCliResult(uid="r1", device_uid=UID_1, result=DIR_IMAGE_OUTPUT)]
            if asa_commands == [f"dir {IMAGE_PATH}"]
            else [CdoCliResult(uid="r2", device_uid=UID_1, error_msg="Directory listing denied")]
        ),
    )

    service = AsaBootImageService(config=object())
    results = service.check_boot_image(device_uids=[UID_1], image_path=IMAGE_PATH)

    assert not isinstance(results, CdoTransaction)
    assert results[UID_1].status == "failed"
    assert "Filesystem inspection failed" in results[UID_1].message


def test_check_boot_image_should_return_transaction_unchanged(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_service_init(monkeypatch)
    failed_tx = CdoTransaction(transactionUid="tx-1", cdoTransactionStatus="ERROR")

    monkeypatch.setattr(
        AsaBootRegistryService,
        "list_boot_registry",
        lambda self, device_uids: failed_tx,
    )

    service = AsaBootImageService(config=object())
    result = service.check_boot_image(device_uids=[UID_1], image_path=IMAGE_PATH)

    assert result is failed_tx


def test_change_boot_image_should_use_boot_command_when_no_existing_entries(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_service_init(monkeypatch)
    boot_calls: list[list[str]] = []
    cli_calls: list[tuple[list[str], list[str]]] = []

    def fake_list_boot_registry(
        self: AsaBootRegistryService, device_uids: list[str]
    ) -> dict[str, AsaBootRegistry]:
        boot_calls.append(list(device_uids))
        if len(boot_calls) == 1:
            return {UID_1: _boot([])}
        return {UID_1: _boot([IMAGE_PATH])}

    def fake_execute_cli(
        self: AsaCommandLineService, *, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        cli_calls.append((list(device_uids), list(asa_commands)))
        if asa_commands == [f"dir {IMAGE_PATH}"]:
            return [CdoCliResult(uid="r1", device_uid=UID_1, result=DIR_IMAGE_OUTPUT)]
        if asa_commands == [f"dir {IMAGE_DIR}"]:
            return [CdoCliResult(uid="r2", device_uid=UID_1, result=DIR_DIRECTORY_OUTPUT)]
        return [CdoCliResult(uid="r2", device_uid=UID_1, result="")]

    monkeypatch.setattr(AsaBootRegistryService, "list_boot_registry", fake_list_boot_registry)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)

    service = AsaBootImageService(config=object())
    results = service.change_boot_image(device_uids=[UID_1], image_path=IMAGE_PATH)

    assert not isinstance(results, CdoTransaction)
    assert results[UID_1].status == "success"
    # No existing entries → no fallback, just the new image
    assert cli_calls[2][1] == [f"boot system {IMAGE_PATH}", "write memory"]


def test_change_boot_image_should_remove_each_existing_entry_before_adding_new_one(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_service_init(monkeypatch)
    cli_calls: list[list[str]] = []
    boot_call_count = {"count": 0}

    def fake_list_boot_registry(
        self: AsaBootRegistryService, device_uids: list[str]
    ) -> dict[str, AsaBootRegistry]:
        boot_call_count["count"] += 1
        if boot_call_count["count"] == 1:
            return {UID_1: _boot([OLD_IMAGE, OLDER_IMAGE])}
        # Verification: expects new primary + previous primary as fallback
        return {UID_1: _boot([IMAGE_PATH, OLD_IMAGE])}

    def fake_execute_cli(
        self: AsaCommandLineService, *, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        cli_calls.append(list(asa_commands))
        if asa_commands == [f"dir {IMAGE_PATH}"]:
            return [CdoCliResult(uid="r1", device_uid=UID_1, result=DIR_IMAGE_OUTPUT)]
        if asa_commands == [f"dir {IMAGE_DIR}"]:
            return [CdoCliResult(uid="r2", device_uid=UID_1, result=DIR_DIRECTORY_OUTPUT)]
        return [CdoCliResult(uid="r2", device_uid=UID_1, result="")]

    monkeypatch.setattr(AsaBootRegistryService, "list_boot_registry", fake_list_boot_registry)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)

    service = AsaBootImageService(config=object())
    results = service.change_boot_image(device_uids=[UID_1], image_path=IMAGE_PATH)

    assert not isinstance(results, CdoTransaction)
    assert results[UID_1].status == "success"
    # Should remove all old entries, add new primary + previous primary as fallback
    assert cli_calls[2] == [
        f"no boot system {OLD_IMAGE}",
        f"no boot system {OLDER_IMAGE}",
        f"boot system {IMAGE_PATH}",
        f"boot system {OLD_IMAGE}",
        "write memory",
    ]


def test_change_boot_image_should_retry_with_bare_no_boot_system_once(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_service_init(monkeypatch)
    cli_calls: list[list[str]] = []
    boot_call_count = {"count": 0}

    def fake_list_boot_registry(
        self: AsaBootRegistryService, device_uids: list[str]
    ) -> dict[str, AsaBootRegistry]:
        boot_call_count["count"] += 1
        if boot_call_count["count"] == 1:
            return {UID_1: _boot([OLD_IMAGE])}
        # Verification: expects new primary + previous primary as fallback
        return {UID_1: _boot([IMAGE_PATH, OLD_IMAGE])}

    def fake_execute_cli(
        self: AsaCommandLineService, *, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        cli_calls.append(list(asa_commands))
        if asa_commands == [f"dir {IMAGE_PATH}"]:
            return [CdoCliResult(uid="r1", device_uid=UID_1, result=DIR_IMAGE_OUTPUT)]
        if asa_commands == [f"dir {IMAGE_DIR}"]:
            return [CdoCliResult(uid="r2", device_uid=UID_1, result=DIR_DIRECTORY_OUTPUT)]
        if asa_commands[0].startswith("no boot system "):
            return [
                CdoCliResult(
                    uid="r2",
                    device_uid=UID_1,
                    result="ERROR: Invalid input detected at '^' marker.",
                )
            ]
        return [CdoCliResult(uid="r3", device_uid=UID_1, result="")]

    monkeypatch.setattr(AsaBootRegistryService, "list_boot_registry", fake_list_boot_registry)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)

    service = AsaBootImageService(config=object())
    results = service.change_boot_image(device_uids=[UID_1], image_path=IMAGE_PATH)

    assert not isinstance(results, CdoTransaction)
    assert results[UID_1].status == "success"
    # Fallback script should also include previous primary as fallback
    assert cli_calls[3] == [
        "no boot system",
        f"boot system {IMAGE_PATH}",
        f"boot system {OLD_IMAGE}",
        "write memory",
    ]


def test_change_boot_image_should_fail_when_both_attempts_fail(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_service_init(monkeypatch)

    monkeypatch.setattr(
        AsaBootRegistryService,
        "list_boot_registry",
        lambda self, device_uids: {UID_1: _boot([OLD_IMAGE])},
    )

    def fake_execute_cli(
        self: AsaCommandLineService, *, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        if asa_commands == [f"dir {IMAGE_PATH}"]:
            return [CdoCliResult(uid="r1", device_uid=UID_1, result=DIR_IMAGE_OUTPUT)]
        if asa_commands == [f"dir {IMAGE_DIR}"]:
            return [CdoCliResult(uid="r2", device_uid=UID_1, result=DIR_DIRECTORY_OUTPUT)]
        return [CdoCliResult(uid="r2", device_uid=UID_1, error_msg="Device rejected command")]

    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)

    service = AsaBootImageService(config=object())
    results = service.change_boot_image(device_uids=[UID_1], image_path=IMAGE_PATH)

    assert not isinstance(results, CdoTransaction)
    assert results[UID_1].status == "failed"
    assert "Device rejected command" in results[UID_1].message


def test_change_boot_image_should_fail_when_verification_mismatches(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_service_init(monkeypatch)
    boot_call_count = {"count": 0}

    def fake_list_boot_registry(
        self: AsaBootRegistryService, device_uids: list[str]
    ) -> dict[str, AsaBootRegistry]:
        boot_call_count["count"] += 1
        if boot_call_count["count"] == 1:
            return {UID_1: _boot([OLD_IMAGE])}
        # Verification returns unexpected 3 entries instead of [IMAGE_PATH, OLD_IMAGE]
        return {UID_1: _boot([IMAGE_PATH, OLD_IMAGE, OLDER_IMAGE])}

    def fake_execute_cli(
        self: AsaCommandLineService, *, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        if asa_commands == [f"dir {IMAGE_PATH}"]:
            return [CdoCliResult(uid="r1", device_uid=UID_1, result=DIR_IMAGE_OUTPUT)]
        if asa_commands == [f"dir {IMAGE_DIR}"]:
            return [CdoCliResult(uid="r2", device_uid=UID_1, result=DIR_DIRECTORY_OUTPUT)]
        return [CdoCliResult(uid="r2", device_uid=UID_1, result="")]

    monkeypatch.setattr(AsaBootRegistryService, "list_boot_registry", fake_list_boot_registry)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)

    service = AsaBootImageService(config=object())
    results = service.change_boot_image(device_uids=[UID_1], image_path=IMAGE_PATH)

    assert not isinstance(results, CdoTransaction)
    assert results[UID_1].status == "failed"
    assert results[UID_1].boot_system_entries_after == [IMAGE_PATH, OLD_IMAGE, OLDER_IMAGE]


def test_change_boot_image_should_return_transaction_from_apply_call(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_service_init(monkeypatch)
    failed_tx = CdoTransaction(transactionUid="tx-apply", cdoTransactionStatus="ERROR")

    monkeypatch.setattr(
        AsaBootRegistryService,
        "list_boot_registry",
        lambda self, device_uids: {UID_1: _boot([OLD_IMAGE])},
    )

    def fake_execute_cli(
        self: AsaCommandLineService, *, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult] | CdoTransaction:
        if asa_commands == [f"dir {IMAGE_PATH}"]:
            return [CdoCliResult(uid="r1", device_uid=UID_1, result=DIR_IMAGE_OUTPUT)]
        if asa_commands == [f"dir {IMAGE_DIR}"]:
            return [CdoCliResult(uid="r2", device_uid=UID_1, result=DIR_DIRECTORY_OUTPUT)]
        return failed_tx

    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)

    service = AsaBootImageService(config=object())
    result = service.change_boot_image(device_uids=[UID_1], image_path=IMAGE_PATH)

    assert result is failed_tx


def test_change_boot_image_should_preserve_device_order_in_results(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_service_init(monkeypatch)
    boot_call_count = {"count": 0}

    def fake_list_boot_registry(
        self: AsaBootRegistryService, device_uids: list[str]
    ) -> dict[str, AsaBootRegistry]:
        boot_call_count["count"] += 1
        if boot_call_count["count"] == 1:
            return {
                UID_1: _boot([IMAGE_PATH]),
                UID_2: _boot([OLD_IMAGE]),
            }
        # Verification: UID_2 should have new primary + previous primary as fallback
        return {UID_2: _boot([IMAGE_PATH, OLD_IMAGE])}

    def fake_execute_cli(
        self: AsaCommandLineService, *, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        if asa_commands == [f"dir {IMAGE_PATH}"]:
            return [
                CdoCliResult(uid="r1", device_uid=UID_1, result=DIR_IMAGE_OUTPUT),
                CdoCliResult(uid="r2", device_uid=UID_2, result=DIR_IMAGE_OUTPUT),
            ]
        if asa_commands == [f"dir {IMAGE_DIR}"]:
            return [
                CdoCliResult(uid="r3", device_uid=UID_1, result=DIR_DIRECTORY_OUTPUT),
                CdoCliResult(uid="r4", device_uid=UID_2, result=DIR_DIRECTORY_OUTPUT),
            ]
        return [CdoCliResult(uid="r3", device_uid=UID_2, result="")]

    monkeypatch.setattr(AsaBootRegistryService, "list_boot_registry", fake_list_boot_registry)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)

    service = AsaBootImageService(config=object())
    results = service.change_boot_image(device_uids=[UID_1, UID_2], image_path=IMAGE_PATH)

    assert not isinstance(results, CdoTransaction)
    assert list(results) == [UID_1, UID_2]
    assert results[UID_1].status == "no_change"
    assert results[UID_2].status == "success"

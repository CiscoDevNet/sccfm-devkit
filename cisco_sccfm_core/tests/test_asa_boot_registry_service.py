# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for cisco_sccfm_core.services.inventory.asa_boot_registry_service — _parse_results."""

from __future__ import annotations

from scc_firewall_manager_sdk import CdoCliResult

from cisco_sccfm_core.services.inventory.asa_boot_registry_service import _parse_results

# ── Sample CLI output fragments ──────────────────────────────────

_SHOW_VERSION = (
    "Cisco Adaptive Security Appliance Software Version 9.22(1)1\n"
    "Compiled on Wed 13-Mar-24 02:50 GMT by builders\n"
    'System image file is "disk0:/asa9221-lfbff-k8.SPA"\n'
    "Configuration register is 0x1\n"
    "Configuration has not been modified since last system restart."
)

_SHOW_RUN_BOOT = "boot system disk0:/asa9221-lfbff-k8.SPA"


# ── Tests ────────────────────────────────────────────────────────


class TestParseResults:
    """Tests for the _parse_results routing function."""

    def test_separate_results_per_command(self) -> None:
        """When the SDK returns one result per command, route each correctly."""
        results = [
            CdoCliResult(
                uid="r1",
                device_uid="dev-1",
                result=_SHOW_VERSION,
                script="show version",
            ),
            CdoCliResult(
                uid="r2",
                device_uid="dev-1",
                result=_SHOW_RUN_BOOT,
                script="show run boot",
            ),
        ]

        parsed = _parse_results(results)
        assert "dev-1" in parsed
        boot = parsed["dev-1"]
        assert boot.system_image_file == "disk0:/asa9221-lfbff-k8.SPA"
        assert boot.config_register == "0x1"
        assert boot.boot_system_entries == ["disk0:/asa9221-lfbff-k8.SPA"]

    def test_combined_result(self) -> None:
        """When the SDK returns a single combined result, both parsers get full text."""
        combined_script = "show version\nshow run boot"
        combined_output = _SHOW_VERSION + "\n" + _SHOW_RUN_BOOT

        results = [
            CdoCliResult(
                uid="r1",
                device_uid="dev-1",
                result=combined_output,
                script=combined_script,
            ),
        ]

        parsed = _parse_results(results)
        assert "dev-1" in parsed
        boot = parsed["dev-1"]
        assert boot.system_image_file == "disk0:/asa9221-lfbff-k8.SPA"
        assert boot.config_register == "0x1"
        assert boot.config_modified is False
        assert boot.boot_system_entries == ["disk0:/asa9221-lfbff-k8.SPA"]

    def test_multiple_devices(self) -> None:
        """Each device's results are grouped independently."""
        results = [
            CdoCliResult(
                uid="r1",
                device_uid="dev-1",
                result=_SHOW_VERSION,
                script="show version",
            ),
            CdoCliResult(
                uid="r2",
                device_uid="dev-1",
                result=_SHOW_RUN_BOOT,
                script="show run boot",
            ),
            CdoCliResult(
                uid="r3",
                device_uid="dev-2",
                result=_SHOW_VERSION,
                script="show version",
            ),
            CdoCliResult(
                uid="r4",
                device_uid="dev-2",
                result="",
                script="show run boot",
            ),
        ]

        parsed = _parse_results(results)
        assert len(parsed) == 2
        assert parsed["dev-1"].boot_system_entries == ["disk0:/asa9221-lfbff-k8.SPA"]
        assert parsed["dev-2"].boot_system_entries == []

    def test_none_result_handled(self) -> None:
        """A result with None output should default to empty string."""
        results = [
            CdoCliResult(
                uid="r1",
                device_uid="dev-1",
                result=None,
                script="show version",
            ),
            CdoCliResult(
                uid="r2",
                device_uid="dev-1",
                result=None,
                script="show run boot",
            ),
        ]

        parsed = _parse_results(results)
        boot = parsed["dev-1"]
        assert boot.system_image_file == "unknown"
        assert boot.compiled_date == "unknown"
        assert boot.config_register == "unknown"
        assert boot.boot_system_entries == []

    def test_error_msg_with_empty_result(self) -> None:
        """When error_msg is set and result is empty, defaults are returned."""
        results = [
            CdoCliResult(
                uid="r1",
                device_uid="dev-1",
                result="",
                error_msg="Device timeout",
                script="show version\nshow run boot",
            ),
        ]

        parsed = _parse_results(results)
        boot = parsed["dev-1"]
        assert boot.system_image_file == "unknown"
        assert boot.boot_system_entries == []

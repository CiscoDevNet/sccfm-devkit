"""Tests for sccfm_core.parsers.asa_boot_registry_parser module."""

from __future__ import annotations

from sccfm_core.models.asa_boot_registry import AsaBootRegistry
from sccfm_core.parsers.asa_boot_registry_parser import parse_boot_registry

# ── Sample outputs ───────────────────────────────────────────────
# Patterns match real ASA output.  All values are fictional.

# ASAv — no config register line, config not modified
SHOW_VERSION_ASAV = (
    "Cisco Adaptive Security Appliance Software Version 9.16(4)42\n"
    "SSP Operating System Version 2.10(1.1611)\n"
    "Device Manager Version 7.18(1)152\n"
    "\n"
    "Compiled on Fri 22-Sep-23 03:23 GMT by builders\n"
    'System image file is "disk0:/asa9-16-4-42-smp-k8.bin"\n'
    'Config file at boot was "startup-config"\n'
    "\n"
    "LABASA up 4 days 18 hours\n"
    "\n"
    "Hardware:   ASAv, 2048 MB RAM, CPU Xeon E5 series 2300 MHz,\n"
    "Internal ATA Compact Flash, 256MB\n"
    "Slot 1: ATA Compact Flash, 256MB\n"
    "BIOS Flash Firmware Hub @ 0x1, 0KB\n"
    "\n"
    "\n"
    " 0: Ext: Management0/0       : address is 0050.aaaa.bbbb, irq 10\n"
    " 1: Ext: GigabitEthernet0/0  : address is 0050.aaaa.cccc, irq 5\n"
    "\n"
    "Serial Number: 9AXXXXXXXXXXX\n"
    "\n"
    "Image type          : Release\n"
    "Key version         : A\n"
    "\n"
    "Configuration has not been modified since last system restart."
)

# FPR-1150 — has config register, config not modified
SHOW_VERSION_FPR = (
    "Cisco Adaptive Security Appliance Software Version 9.22(1)1\n"
    "SSP Operating System Version 2.14(1.145)\n"
    "Device Manager Version 7.22(1)152\n"
    "\n"
    "Compiled on Wed 13-Mar-24 02:50 GMT by builders\n"
    'System image file is "disk0:/installables/switch/fxos-k8-fp1k-lfbff.2.14.1.145.SPA"\n'
    'Config file at boot was "startup-config"\n'
    "\n"
    "LABASA up 125 days 3 hours\n"
    "\n"
    "Hardware:   FPR-1150, 16384 MB RAM, CPU Xeon E3-1200 v6/7th Gen Core 2300 MHz\n"
    "\n"
    "Configuration register is 0x1\n"
    "Configuration has not been modified since last system restart."
)

# ASA 5516 — config register present, config modified (line absent)
SHOW_VERSION_5516 = (
    "Cisco Adaptive Security Appliance Software Version 9.18(2)\n"
    "Firepower Extensible Operating System Version 2.12(0.498)\n"
    "\n"
    "Compiled on Thu 08-Jun-23 15:20 UTC by builders\n"
    'System image file is "disk0:/asa9182-lfbff-k8.SPA"\n'
    'Config file at boot was "startup-config"\n'
    "\n"
    "LABASA up 42 days 18 hours\n"
    "\n"
    "Hardware:   FPR-2110, 8192 MB RAM, CPU Atom C3000 2400 MHz\n"
    "\n"
    "Configuration register is 0x41"
)

SHOW_RUN_BOOT_SINGLE = "boot system disk0:/asa9-16-4-42-smp-k8.bin"

SHOW_RUN_BOOT_MULTI = (
    "boot system disk0:/asa9-16-4-42-smp-k8.bin\n"
    "boot system disk0:/asa9-16-3-19-smp-k8.bin\n"
    "boot system disk0:/asa9-14-3-11-smp-k8.bin"
)

SHOW_RUN_BOOT_EMPTY = ""


# ── Tests ────────────────────────────────────────────────────────


class TestParseBootRegistry:
    """Tests for parse_boot_registry()."""

    # -- ASAv (no config register line) ----------------------------

    def test_asav_system_image(self) -> None:
        result = parse_boot_registry(SHOW_VERSION_ASAV, SHOW_RUN_BOOT_EMPTY)
        assert result.system_image_file == "disk0:/asa9-16-4-42-smp-k8.bin"

    def test_asav_compiled_date(self) -> None:
        result = parse_boot_registry(SHOW_VERSION_ASAV, SHOW_RUN_BOOT_EMPTY)
        assert result.compiled_date == "Fri 22-Sep-23 03:23 GMT"

    def test_asav_no_config_register(self) -> None:
        """ASAv output has no 'Configuration register is' line."""
        result = parse_boot_registry(SHOW_VERSION_ASAV, SHOW_RUN_BOOT_EMPTY)
        assert result.config_register == "unknown"

    def test_asav_config_not_modified(self) -> None:
        result = parse_boot_registry(SHOW_VERSION_ASAV, SHOW_RUN_BOOT_EMPTY)
        assert result.config_modified is False

    # -- FPR hardware (with config register) -----------------------

    def test_fpr_system_image(self) -> None:
        result = parse_boot_registry(SHOW_VERSION_FPR, SHOW_RUN_BOOT_EMPTY)
        assert (
            result.system_image_file
            == "disk0:/installables/switch/fxos-k8-fp1k-lfbff.2.14.1.145.SPA"
        )

    def test_fpr_config_register(self) -> None:
        result = parse_boot_registry(SHOW_VERSION_FPR, SHOW_RUN_BOOT_EMPTY)
        assert result.config_register == "0x1"

    def test_fpr_config_not_modified(self) -> None:
        result = parse_boot_registry(SHOW_VERSION_FPR, SHOW_RUN_BOOT_EMPTY)
        assert result.config_modified is False

    # -- Config modified (line absent) -----------------------------

    def test_config_modified_when_line_absent(self) -> None:
        result = parse_boot_registry(SHOW_VERSION_5516, SHOW_RUN_BOOT_EMPTY)
        assert result.config_modified is True

    def test_config_register_hex(self) -> None:
        result = parse_boot_registry(SHOW_VERSION_5516, SHOW_RUN_BOOT_EMPTY)
        assert result.config_register == "0x41"

    # -- Boot entries ----------------------------------------------

    def test_single_boot_entry(self) -> None:
        result = parse_boot_registry(SHOW_VERSION_FPR, SHOW_RUN_BOOT_SINGLE)
        assert result.boot_system_entries == ["disk0:/asa9-16-4-42-smp-k8.bin"]

    def test_multiple_boot_entries(self) -> None:
        result = parse_boot_registry(SHOW_VERSION_FPR, SHOW_RUN_BOOT_MULTI)
        assert result.boot_system_entries == [
            "disk0:/asa9-16-4-42-smp-k8.bin",
            "disk0:/asa9-16-3-19-smp-k8.bin",
            "disk0:/asa9-14-3-11-smp-k8.bin",
        ]

    def test_empty_boot_entries(self) -> None:
        result = parse_boot_registry(SHOW_VERSION_FPR, SHOW_RUN_BOOT_EMPTY)
        assert result.boot_system_entries == []

    # -- Empty / None inputs (device offline or no output) ---------

    def test_both_outputs_empty(self) -> None:
        """Both commands returned empty strings — all fields default."""
        result = parse_boot_registry("", "")
        assert result.system_image_file == "unknown"
        assert result.compiled_date == "unknown"
        assert result.config_register == "unknown"
        assert result.config_modified is True  # line absent → modified
        assert result.boot_system_entries == []

    def test_show_version_empty_boot_has_entries(self) -> None:
        """show version empty but show run boot has data."""
        result = parse_boot_registry("", SHOW_RUN_BOOT_MULTI)
        assert result.system_image_file == "unknown"
        assert len(result.boot_system_entries) == 3

    def test_show_version_present_boot_empty(self) -> None:
        """show version has data but show run boot is empty."""
        result = parse_boot_registry(SHOW_VERSION_ASAV, "")
        assert result.system_image_file == "disk0:/asa9-16-4-42-smp-k8.bin"
        assert result.boot_system_entries == []

    def test_combined_output_parsed_correctly(self) -> None:
        """SDK may return both outputs concatenated in a single result.

        The parser must still extract all fields when the same combined
        text is passed as both show_version and show_run_boot.
        """
        combined = SHOW_VERSION_FPR + "\n" + SHOW_RUN_BOOT_MULTI
        result = parse_boot_registry(combined, combined)
        assert (
            result.system_image_file
            == "disk0:/installables/switch/fxos-k8-fp1k-lfbff.2.14.1.145.SPA"
        )
        assert result.compiled_date == "Wed 13-Mar-24 02:50 GMT"
        assert result.config_register == "0x1"
        assert result.config_modified is False
        assert result.boot_system_entries == [
            "disk0:/asa9-16-4-42-smp-k8.bin",
            "disk0:/asa9-16-3-19-smp-k8.bin",
            "disk0:/asa9-14-3-11-smp-k8.bin",
        ]

    # -- Dataclass integrity ---------------------------------------

    def test_result_is_frozen_dataclass(self) -> None:
        result = parse_boot_registry(SHOW_VERSION_FPR, SHOW_RUN_BOOT_EMPTY)
        assert isinstance(result, AsaBootRegistry)
        # Verify frozen — assignment must raise.
        try:
            result.system_image_file = "changed"
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass

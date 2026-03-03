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


# ── Edge-case tests ──────────────────────────────────────────────


class TestCRLFLineEndings:
    """Devices commonly return CRLF (\\r\\n) line endings."""

    SHOW_VERSION_CRLF = SHOW_VERSION_ASAV.replace("\n", "\r\n")
    SHOW_RUN_BOOT_CRLF = SHOW_RUN_BOOT_MULTI.replace("\n", "\r\n")

    def test_system_image_with_crlf(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_CRLF, SHOW_RUN_BOOT_EMPTY)
        assert result.system_image_file == "disk0:/asa9-16-4-42-smp-k8.bin"

    def test_compiled_date_with_crlf(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_CRLF, SHOW_RUN_BOOT_EMPTY)
        assert result.compiled_date == "Fri 22-Sep-23 03:23 GMT"

    def test_config_not_modified_with_crlf(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_CRLF, SHOW_RUN_BOOT_EMPTY)
        assert result.config_modified is False

    def test_boot_entries_with_crlf(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_CRLF, self.SHOW_RUN_BOOT_CRLF)
        assert len(result.boot_system_entries) == 3
        assert result.boot_system_entries[0] == "disk0:/asa9-16-4-42-smp-k8.bin"


class TestPendingConfigRegister:
    """ASA shows '(will be 0xNN at next reload)' when a change is staged."""

    SHOW_VERSION_PENDING = (
        "Cisco Adaptive Security Appliance Software Version 9.18(2)\n"
        "\n"
        "Compiled on Thu 08-Jun-23 15:20 UTC by builders\n"
        'System image file is "disk0:/asa9182-lfbff-k8.SPA"\n'
        "\n"
        "Hardware:   FPR-2110, 8192 MB RAM, CPU Atom C3000 2400 MHz\n"
        "\n"
        "Configuration register is 0x1 (will be 0x41 at next reload)\n"
        "Configuration has not been modified since last system restart."
    )

    def test_captures_current_register_not_pending(self) -> None:
        """Parser should capture 0x1, ignoring the pending 0x41."""
        result = parse_boot_registry(self.SHOW_VERSION_PENDING, SHOW_RUN_BOOT_EMPTY)
        assert result.config_register == "0x1"

    def test_config_not_modified_still_detected(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_PENDING, SHOW_RUN_BOOT_EMPTY)
        assert result.config_modified is False


class TestBootImagePrefix:
    """System image with boot:/ prefix (ASAv 9.23+)."""

    SHOW_VERSION_BOOT_PREFIX = (
        "Cisco Adaptive Security Appliance Software Version 9.23(1)\n"
        "\n"
        "Compiled on Mon 03-Mar-25 15:42 GMT by builders\n"
        'System image file is "boot:/asa9231-smp-k8.bin"\n'
        "\n"
        "Hardware:   ASAv, 7680 MB RAM, CPU Xeon 4100/6100/8100 series 3000 MHz\n"
        "\n"
        "Configuration has not been modified since last system restart."
    )

    def test_boot_prefix_image_captured(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_BOOT_PREFIX, SHOW_RUN_BOOT_EMPTY)
        assert result.system_image_file == "boot:/asa9231-smp-k8.bin"


class TestCompiledDateVariants:
    """Compiled line can have different timezones and formats."""

    def _make_show_version(self, compiled_line: str) -> str:
        return (
            "Cisco Adaptive Security Appliance Software Version 9.18(2)\n"
            f"{compiled_line}\n"
            'System image file is "disk0:/asa9182-k8.bin"\n'
            "Configuration has not been modified since last system restart."
        )

    def test_compiled_with_pdt_timezone(self) -> None:
        text = self._make_show_version("Compiled on Mon 23-Sep-19 09:38 PDT by builders")
        result = parse_boot_registry(text, SHOW_RUN_BOOT_EMPTY)
        assert result.compiled_date == "Mon 23-Sep-19 09:38 PDT"

    def test_compiled_with_utc_timezone(self) -> None:
        text = self._make_show_version("Compiled on Thu 08-Jun-23 15:20 UTC by builders")
        result = parse_boot_registry(text, SHOW_RUN_BOOT_EMPTY)
        assert result.compiled_date == "Thu 08-Jun-23 15:20 UTC"

    def test_compiled_without_by_builders(self) -> None:
        """Some ASA versions omit 'by builders'."""
        text = self._make_show_version("Compiled on Thu 08-Jun-23 15:20 UTC")
        result = parse_boot_registry(text, SHOW_RUN_BOOT_EMPTY)
        assert result.compiled_date == "Thu 08-Jun-23 15:20 UTC"

    def test_compiled_with_trailing_whitespace(self) -> None:
        text = self._make_show_version("Compiled on Fri 22-Sep-23 03:23 GMT by builders   ")
        result = parse_boot_registry(text, SHOW_RUN_BOOT_EMPTY)
        assert result.compiled_date == "Fri 22-Sep-23 03:23 GMT"


class TestBootSystemEntryVariants:
    """Various boot system entry formats from show run boot."""

    def test_indented_boot_entries(self) -> None:
        """show run boot may indent entries."""
        text = (
            "  boot system disk0:/asa9-16-4-42-smp-k8.bin\n"
            "  boot system disk0:/asa9-14-3-11-smp-k8.bin"
        )
        result = parse_boot_registry(SHOW_VERSION_ASAV, text)
        assert result.boot_system_entries == [
            "disk0:/asa9-16-4-42-smp-k8.bin",
            "disk0:/asa9-14-3-11-smp-k8.bin",
        ]

    def test_boot_entry_with_boot_prefix(self) -> None:
        text = "boot system boot:/asa9231-smp-k8.bin"
        result = parse_boot_registry(SHOW_VERSION_ASAV, text)
        assert result.boot_system_entries == ["boot:/asa9231-smp-k8.bin"]

    def test_boot_entry_with_spa_suffix(self) -> None:
        text = "boot system disk0:/cisco-asa-fp1k.9.20.2.10.SPA"
        result = parse_boot_registry(SHOW_VERSION_FPR, text)
        assert result.boot_system_entries == ["disk0:/cisco-asa-fp1k.9.20.2.10.SPA"]

    def test_boot_entries_with_blank_lines(self) -> None:
        """Blank lines between entries should not produce extra entries."""
        text = (
            "boot system disk0:/asa9-16-4-42-smp-k8.bin\n"
            "\n"
            "boot system disk0:/asa9-14-3-11-smp-k8.bin\n"
            "\n"
        )
        result = parse_boot_registry(SHOW_VERSION_ASAV, text)
        assert len(result.boot_system_entries) == 2

    def test_boot_entries_ignores_non_boot_lines(self) -> None:
        """Other lines in show run boot should be ignored."""
        text = (
            "! some comment\n"
            "boot system disk0:/asa9-16-4-42-smp-k8.bin\n"
            "hostname LABASA\n"
            "boot system disk0:/asa9-14-3-11-smp-k8.bin"
        )
        result = parse_boot_registry(SHOW_VERSION_ASAV, text)
        assert result.boot_system_entries == [
            "disk0:/asa9-16-4-42-smp-k8.bin",
            "disk0:/asa9-14-3-11-smp-k8.bin",
        ]


class TestConfigRegisterHexVariants:
    """Validate different hex register values are captured."""

    def _make_show_version(self, register_line: str) -> str:
        return (
            "Cisco Adaptive Security Appliance Software Version 9.18(2)\n"
            "Compiled on Thu 08-Jun-23 15:20 UTC by builders\n"
            'System image file is "disk0:/asa9182-k8.bin"\n'
            f"{register_line}\n"
            "Configuration has not been modified since last system restart."
        )

    def test_register_0x1(self) -> None:
        text = self._make_show_version("Configuration register is 0x1")
        result = parse_boot_registry(text, SHOW_RUN_BOOT_EMPTY)
        assert result.config_register == "0x1"

    def test_register_0x41(self) -> None:
        text = self._make_show_version("Configuration register is 0x41")
        result = parse_boot_registry(text, SHOW_RUN_BOOT_EMPTY)
        assert result.config_register == "0x41"

    def test_register_0x2102(self) -> None:
        text = self._make_show_version("Configuration register is 0x2102")
        result = parse_boot_registry(text, SHOW_RUN_BOOT_EMPTY)
        assert result.config_register == "0x2102"

    def test_register_uppercase_hex(self) -> None:
        text = self._make_show_version("Configuration register is 0x1A")
        result = parse_boot_registry(text, SHOW_RUN_BOOT_EMPTY)
        assert result.config_register == "0x1A"


class TestWhitespaceEdgeCases:
    """Whitespace-only and extra-whitespace inputs."""

    def test_whitespace_only_show_version(self) -> None:
        result = parse_boot_registry("   \n  \n  ", SHOW_RUN_BOOT_EMPTY)
        assert result.system_image_file == "unknown"
        assert result.compiled_date == "unknown"
        assert result.config_register == "unknown"
        assert result.config_modified is True

    def test_whitespace_only_show_run_boot(self) -> None:
        result = parse_boot_registry(SHOW_VERSION_ASAV, "   \n  \n  ")
        assert result.boot_system_entries == []

    def test_extra_whitespace_in_system_image_line(self) -> None:
        """Extra spacing between 'is' and the opening quote."""
        text = (
            "Compiled on Fri 22-Sep-23 03:23 GMT by builders\n"
            'System image file is   "disk0:/asa9-16-4-42-smp-k8.bin"\n'
            "Configuration has not been modified since last system restart."
        )
        result = parse_boot_registry(text, SHOW_RUN_BOOT_EMPTY)
        assert result.system_image_file == "disk0:/asa9-16-4-42-smp-k8.bin"


class TestOldAsaVersion:
    """Older ASA (e.g. 9.13) output from real tenant."""

    SHOW_VERSION_ASA_913 = (
        "Cisco Adaptive Security Appliance Software Version 9.13(1)\n"
        "Device Manager Version 7.13(1)\n"
        "\n"
        "Compiled on Mon 23-Sep-19 09:38 PDT by builders\n"
        'System image file is "disk0:/asa9-13-1-smp-k8.bin"\n'
        'Config file at boot was "startup-config"\n'
        "\n"
        "Hardware:   ASAv, 2048 MB RAM, CPU Xeon E5 series 2300 MHz,\n"
        "\n"
        "Serial Number: 9ACVE8GK12Q\n"
    )

    SHOW_RUN_BOOT_913 = (
        "boot system disk0:/asa9-13-1-smp-k8.bin\n"
        "boot system disk0:/asa9-12-3-9-smp-k8.bin\n"
        "boot system disk0:/asa9-12-3-smp-k8.bin"
    )

    def test_old_asa_system_image(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_ASA_913, self.SHOW_RUN_BOOT_913)
        assert result.system_image_file == "disk0:/asa9-13-1-smp-k8.bin"

    def test_old_asa_compiled_pdt(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_ASA_913, self.SHOW_RUN_BOOT_913)
        assert result.compiled_date == "Mon 23-Sep-19 09:38 PDT"

    def test_old_asa_no_config_register(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_ASA_913, self.SHOW_RUN_BOOT_913)
        assert result.config_register == "unknown"

    def test_old_asa_config_modified(self) -> None:
        """No 'Configuration has not been modified' line -> modified."""
        result = parse_boot_registry(self.SHOW_VERSION_ASA_913, self.SHOW_RUN_BOOT_913)
        assert result.config_modified is True

    def test_old_asa_three_boot_entries(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_ASA_913, self.SHOW_RUN_BOOT_913)
        assert result.boot_system_entries == [
            "disk0:/asa9-13-1-smp-k8.bin",
            "disk0:/asa9-12-3-9-smp-k8.bin",
            "disk0:/asa9-12-3-smp-k8.bin",
        ]


class TestFPR1010RealOutput:
    """FPR-1010 output based on real device (u73c01p05-asa-1010-1)."""

    SHOW_VERSION_FPR1010 = (
        "Cisco Adaptive Security Appliance Software Version 9.20(2)10\n"
        "Firepower Extensible Operating System Version 2.14(1.145)\n"
        "Device Manager Version 7.20(2)\n"
        "\n"
        "Compiled on Wed 13-Mar-24 02:50 GMT by builders\n"
        'System image file is "disk0:/installables/switch/'
        'fxos-k8-fp1k-lfbff.2.14.1.145.SPA"\n'
        'Config file at boot was "startup-config"\n'
        "\n"
        "Hardware:   FPR-1010, 7066 MB RAM, CPU Atom C3000 series 2200 MHz\n"
        "\n"
        "Configuration register is 0x1\n"
        "Configuration has not been modified since last system restart."
    )

    SHOW_RUN_BOOT_FPR1010 = "boot system disk0:/cisco-asa-fp1k.9.20.2.10.SPA"

    def test_fpr1010_deep_path_image(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_FPR1010, self.SHOW_RUN_BOOT_FPR1010)
        assert result.system_image_file == (
            "disk0:/installables/switch/fxos-k8-fp1k-lfbff.2.14.1.145.SPA"
        )

    def test_fpr1010_config_register(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_FPR1010, self.SHOW_RUN_BOOT_FPR1010)
        assert result.config_register == "0x1"

    def test_fpr1010_not_modified(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_FPR1010, self.SHOW_RUN_BOOT_FPR1010)
        assert result.config_modified is False

    def test_fpr1010_boot_entry_spa_suffix(self) -> None:
        result = parse_boot_registry(self.SHOW_VERSION_FPR1010, self.SHOW_RUN_BOOT_FPR1010)
        assert result.boot_system_entries == ["disk0:/cisco-asa-fp1k.9.20.2.10.SPA"]

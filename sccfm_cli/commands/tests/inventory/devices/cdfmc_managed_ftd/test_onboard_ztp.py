"""Tests for the ``sccfm_cli inventory devices cdfmc-managed-ftd onboard-ztp`` command."""

from __future__ import annotations

import json
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import Device, DevicePage, EntityType, ZtpOnboardingInput

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services import InventoryService
from sccfm_core.services.inventory import FtdZtpOnboardService

_BASE_ARGS = [
    "inventory",
    "devices",
    "cdfmc-managed-ftd",
    "onboard-ztp",
    "--name",
    "branch-ftd-01",
    "--serial-number",
    "FTD1234567890",
    "--licenses",
    "BASE",
    "--fmc-access-policy-uid",
    "policy-uid-abc",
]


def _fake_device() -> Device:
    return Device(
        uid="device-uid-999",
        name="branch-ftd-01",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        serial="FTD1234567890",
    )


def _empty_device_page(
    self: InventoryService, *, limit: int, offset: int, query: str | None = None
) -> DevicePage:
    return DevicePage(count=0, items=[], limit=limit, offset=offset)


def _existing_device_page(
    self: InventoryService, *, limit: int, offset: int, query: str | None = None
) -> DevicePage:
    """Returns the same device for every query — simulates name+serial pointing to same uid."""
    return DevicePage(count=1, items=[_fake_device()], limit=limit, offset=offset)


def _stub_ztp_service_init(self: FtdZtpOnboardService, config: Any) -> None:
    return None


# ── Successful onboard ──────────────────────────────────────────


class TestSuccessfulOnboard:
    def test_should_onboard_and_return_uid_table(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(InventoryService, "get_devices", _empty_device_page)
        monkeypatch.setattr(FtdZtpOnboardService, "__init__", _stub_ztp_service_init)

        captured: dict[str, Any] = {}

        def fake_onboard(
            self: FtdZtpOnboardService, ztp_onboarding_input: ZtpOnboardingInput
        ) -> Device:
            captured["input"] = ztp_onboarding_input
            return _fake_device()

        monkeypatch.setattr(FtdZtpOnboardService, "onboard_ftd_ztp", fake_onboard)

        result = cli_runner.invoke(cli, _BASE_ARGS + ["--format", "table"])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "device-uid-999" in result.output
        assert captured["input"].name == "branch-ftd-01"
        assert captured["input"].serial_number == "FTD1234567890"
        assert captured["input"].licenses == ["BASE"]
        assert captured["input"].fmc_access_policy_uid == "policy-uid-abc"

    def test_should_onboard_and_return_uid_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(InventoryService, "get_devices", _empty_device_page)
        monkeypatch.setattr(FtdZtpOnboardService, "__init__", _stub_ztp_service_init)

        monkeypatch.setattr(
            FtdZtpOnboardService,
            "onboard_ftd_ztp",
            lambda self, ztp_onboarding_input: _fake_device(),
        )

        result = cli_runner.invoke(cli, _BASE_ARGS + ["--format", "json"])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output)
        assert payload["uid"] == "device-uid-999"

    def test_should_pass_optional_params(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(InventoryService, "get_devices", _empty_device_page)
        monkeypatch.setattr(FtdZtpOnboardService, "__init__", _stub_ztp_service_init)

        captured: dict[str, Any] = {}

        def fake_onboard(
            self: FtdZtpOnboardService, ztp_onboarding_input: ZtpOnboardingInput
        ) -> Device:
            captured["input"] = ztp_onboarding_input
            return _fake_device()

        monkeypatch.setattr(FtdZtpOnboardService, "onboard_ftd_ztp", fake_onboard)

        result = cli_runner.invoke(
            cli,
            _BASE_ARGS
            + [
                "--admin-password",
                "s3cr3t",
                "--device-group-uid",
                "group-uid-xyz",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured["input"].admin_password == "s3cr3t"
        assert captured["input"].device_group_uid == "group-uid-xyz"

    def test_should_support_multiple_licenses(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(InventoryService, "get_devices", _empty_device_page)
        monkeypatch.setattr(FtdZtpOnboardService, "__init__", _stub_ztp_service_init)

        captured: dict[str, Any] = {}

        def fake_onboard(
            self: FtdZtpOnboardService, ztp_onboarding_input: ZtpOnboardingInput
        ) -> Device:
            captured["input"] = ztp_onboarding_input
            return _fake_device()

        monkeypatch.setattr(FtdZtpOnboardService, "onboard_ftd_ztp", fake_onboard)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "onboard-ztp",
                "--name",
                "branch-ftd-01",
                "--serial-number",
                "FTD1234567890",
                "--licenses",
                "BASE",
                "--licenses",
                "THREAT",
                "--fmc-access-policy-uid",
                "policy-uid-abc",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert set(captured["input"].licenses) == {"BASE", "THREAT"}


# ── Check mode ─────────────────────────────────────────────────


class TestCheckMode:
    def test_check_device_not_found_table(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(InventoryService, "get_devices", _empty_device_page)

        result = cli_runner.invoke(cli, _BASE_ARGS + ["--check", "--format", "table"])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "No conflicts found" in result.output

    def test_check_device_not_found_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(InventoryService, "get_devices", _empty_device_page)

        result = cli_runner.invoke(cli, _BASE_ARGS + ["--check", "--format", "json"])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output)
        assert payload["can_proceed"] is True
        assert payload["exists"] is False
        assert payload["reason"] == "not_found"
        assert payload["operation"] == "onboard-ztp"
        assert payload["identifier"]["name"] == "branch-ftd-01"
        assert payload["identifier"]["serial_number"] == "FTD1234567890"

    def test_check_device_already_exists_table(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(InventoryService, "get_devices", _existing_device_page)

        result = cli_runner.invoke(cli, _BASE_ARGS + ["--check", "--format", "table"])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "already onboarded" in result.output

    def test_check_device_already_exists_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(InventoryService, "get_devices", _existing_device_page)

        result = cli_runner.invoke(cli, _BASE_ARGS + ["--check", "--format", "json"])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output)
        assert payload["can_proceed"] is False
        assert payload["exists"] is True
        assert payload["reason"] == "already_exists"
        assert payload["device"]["uid"] == "device-uid-999"

    def test_check_name_conflict_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """--check should report name_conflict when name is taken by a different serial."""
        name_device = Device(
            uid="uid-other",
            name="branch-ftd-01",
            deviceType=EntityType.CDFMC_MANAGED_FTD,
            serial="DIFFERENT_SERIAL",
        )

        monkeypatch.setattr(
            InventoryService,
            "get_devices",
            lambda self, *, limit, offset, query=None: DevicePage(
                count=1, items=[name_device], limit=limit, offset=offset
            ),
        )

        result = cli_runner.invoke(cli, _BASE_ARGS + ["--check", "--format", "json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["can_proceed"] is False
        assert payload["exists"] is True
        assert payload["reason"] == "name_conflict"
        assert payload["device"]["uid"] == "uid-other"


# ── Conflict detection ──────────────────────────────────────────


class TestConflictDetection:
    def test_should_fail_when_name_taken_by_different_serial(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """onboard-ztp should fail when the name is taken by a device with a different serial."""
        name_device = Device(
            uid="uid-other",
            name="branch-ftd-01",
            deviceType=EntityType.CDFMC_MANAGED_FTD,
            serial="DIFFERENT_SERIAL",
        )

        monkeypatch.setattr(
            InventoryService,
            "get_devices",
            lambda self, *, limit, offset, query=None: DevicePage(
                count=1, items=[name_device], limit=limit, offset=offset
            ),
        )

        result = cli_runner.invoke(cli, _BASE_ARGS)

        assert result.exit_code != 0
        assert "already exists with a different serial" in result.output

    def test_should_fail_when_device_already_exists(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """onboard-ztp should fail when the exact same device (name+serial) is already present."""
        monkeypatch.setattr(InventoryService, "get_devices", _existing_device_page)

        result = cli_runner.invoke(cli, _BASE_ARGS)

        assert result.exit_code != 0
        assert "already onboarded" in result.output


# ── Validation ─────────────────────────────────────────────────


class TestValidation:
    def test_should_fail_when_device_name_already_exists(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(InventoryService, "get_devices", _existing_device_page)

        result = cli_runner.invoke(cli, _BASE_ARGS + ["--format", "json"])

        assert result.exit_code != 0
        assert "already" in result.output

    def test_should_fail_when_name_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
    ) -> None:
        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "onboard-ztp",
                "--serial-number",
                "FTD1234567890",
                "--licenses",
                "BASE",
                "--fmc-access-policy-uid",
                "policy-uid-abc",
            ],
        )

        assert result.exit_code != 0

    def test_should_fail_when_serial_number_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
    ) -> None:
        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "onboard-ztp",
                "--name",
                "branch-ftd-01",
                "--licenses",
                "BASE",
                "--fmc-access-policy-uid",
                "policy-uid-abc",
            ],
        )

        assert result.exit_code != 0

    def test_should_fail_when_fmc_access_policy_uid_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
    ) -> None:
        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "onboard-ztp",
                "--name",
                "branch-ftd-01",
                "--serial-number",
                "FTD1234567890",
                "--licenses",
                "BASE",
            ],
        )

        assert result.exit_code != 0

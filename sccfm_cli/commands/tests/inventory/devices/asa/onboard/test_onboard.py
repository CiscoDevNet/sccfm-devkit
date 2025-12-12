from __future__ import annotations

import json
from typing import Any, Callable

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import Device, DevicePage, EntityType

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core import InventoryService
from sccfm_core.services.inventory import AsaOnboardService


@pytest.fixture
def empty_device_page() -> Callable[..., DevicePage]:
    """Returns a function that returns an empty DevicePage."""
    return lambda self, limit, offset, query=None: DevicePage(
        count=0, items=[], limit=limit, offset=offset
    )


@pytest.fixture
def stub_asa_onboard_init() -> Callable[..., None]:
    """Returns a stub for AsaOnboardService __init__."""
    return lambda self, config: None


@pytest.fixture
def captured_params() -> dict[str, Any]:
    """Returns a dict to capture test parameters."""
    return {}


def test_should_onboard_asa(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    empty_device_page: Callable[..., DevicePage],
    stub_asa_onboard_init: Callable[..., None],
    captured_params: dict[str, Any],
) -> None:
    """Onboard command should successfully onboard an ASA device."""
    expected_device = Device(
        uid="asa-uid-123",
        name="test-asa",
        device_type=EntityType.ASA,
    )

    monkeypatch.setattr(InventoryService, "get_devices", empty_device_page)
    monkeypatch.setattr(
        AsaOnboardService,
        "onboard_asa",
        lambda self, asa_create_or_update_input: (
            captured_params.update({"input": asa_create_or_update_input}) or expected_device
        ),
    )
    monkeypatch.setattr(AsaOnboardService, "__init__", stub_asa_onboard_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "onboard",
            "--name",
            "test-asa",
            "--device-address",
            "192.168.1.1:443",
            "--username",
            "admin",
            "--password",
            "test-password",
            "--connector-type",
            "CDG",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify onboard service was called
    assert "input" in captured_params
    asa_input = captured_params["input"]
    assert asa_input.name == "test-asa"
    assert asa_input.device_address == "192.168.1.1:443"
    assert asa_input.username == "admin"
    assert asa_input.password == "test-password"

    # Verify JSON output
    payload = json.loads(result.output)
    assert payload["uid"] == "asa-uid-123"
    assert payload["name"] == "test-asa"


def test_should_fail_if_connector_name_not_specified_and_connector_type_sdc(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
) -> None:
    """Onboard command should fail when connector_type is SDC but connector_name is not provided."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "onboard",
            "--name",
            "test-asa",
            "--device-address",
            "192.168.1.1:443",
            "--username",
            "admin",
            "--password",
            "test-password",
            "--connector-type",
            "SDC",
        ],
    )

    assert result.exit_code != 0
    assert "--connector-name is required when --connector-type is SDC" in result.output


@pytest.mark.parametrize(
    "device_address,expected_error",
    [
        ("192.168.1.1", "Device address must be in the format host:port"),
        (":443", "Host cannot be empty"),
        ("192.168.1.1:", "Port must be a valid integer"),
        ("192.168.1.1:abc", "Port must be a valid integer"),
        ("192.168.1.1:0", "Port must be between 1 and 65535"),
        ("192.168.1.1:65536", "Port must be between 1 and 65535"),
        ("192.168.1.1:-1", "Port must be between 1 and 65535"),
    ],
)
def test_should_fail_if_device_address_invalid(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    device_address: str,
    expected_error: str,
) -> None:
    """Onboard command should fail when device address is invalid."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "onboard",
            "--name",
            "test-asa",
            "--device-address",
            device_address,
            "--username",
            "admin",
            "--password",
            "test-password",
            "--connector-type",
            "CDG",
        ],
    )

    assert result.exit_code != 0
    assert expected_error in result.output


def test_should_fail_if_device_already_exists(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Onboard command should fail when a device with the same name already exists."""
    existing_device = Device(
        uid="existing-uid",
        name="test-asa",
        device_type=EntityType.ASA,
    )

    monkeypatch.setattr(
        InventoryService,
        "get_devices",
        lambda self, limit, offset, query=None: DevicePage(
            count=1, items=[existing_device], limit=limit, offset=offset
        ),
    )

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "onboard",
            "--name",
            "test-asa",
            "--device-address",
            "192.168.1.1:443",
            "--username",
            "admin",
            "--password",
            "test-password",
            "--connector-type",
            "CDG",
        ],
    )

    assert result.exit_code != 0
    assert "ASA device with name test-asa already exists" in result.output


def test_should_display_table_output_by_default(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    empty_device_page: Callable[..., DevicePage],
    stub_asa_onboard_init: Callable[..., None],
) -> None:
    """Onboard command should display formatted output by default."""
    expected_device = Device(
        uid="asa-uid-456",
        name="my-asa",
        device_type=EntityType.ASA,
    )

    monkeypatch.setattr(InventoryService, "get_devices", empty_device_page)
    monkeypatch.setattr(
        AsaOnboardService,
        "onboard_asa",
        lambda self, asa_create_or_update_input: expected_device,
    )
    monkeypatch.setattr(AsaOnboardService, "__init__", stub_asa_onboard_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "onboard",
            "--name",
            "my-asa",
            "--device-address",
            "10.0.0.1:443",
            "--username",
            "admin",
            "--password",
            "test-password",
            "--connector-type",
            "CDG",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "Successfully onboarded ASA: my-asa" in result.output
    assert "UID: asa-uid-456" in result.output


def test_should_onboard_asa_with_sdc_connector(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    empty_device_page: Callable[..., DevicePage],
    stub_asa_onboard_init: Callable[..., None],
    captured_params: dict[str, Any],
) -> None:
    expected_device = Device(
        uid="asa-uid-789",
        name="sdc-asa",
        device_type=EntityType.ASA,
    )

    monkeypatch.setattr(InventoryService, "get_devices", empty_device_page)
    monkeypatch.setattr(
        AsaOnboardService,
        "onboard_asa",
        lambda self, asa_create_or_update_input: (
            captured_params.update({"input": asa_create_or_update_input}) or expected_device
        ),
    )
    monkeypatch.setattr(AsaOnboardService, "__init__", stub_asa_onboard_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "onboard",
            "--name",
            "sdc-asa",
            "--device-address",
            "192.168.2.1:443",
            "--username",
            "admin",
            "--password",
            "test-password",
            "--connector-type",
            "SDC",
            "--connector-name",
            "my-sdc-connector",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify SDC connector was properly configured
    asa_input = captured_params["input"]
    assert str(asa_input.connector_type.value) == "SDC"
    assert asa_input.connector_name == "my-sdc-connector"

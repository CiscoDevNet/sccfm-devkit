# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import (
    CdoCliResult,
    ConfigState,
    ConnectivityState,
    Device,
    EntityType,
)

from cisco_sccfm_cli.models import Config
from cisco_sccfm_cli.services import ConfigService
from cisco_sccfm_core.services import InventoryService


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provides a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def config_path(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    """Creates a temporary config file and sets SCCFM_CONFIG env var."""
    path = tmp_path / "config.json"
    monkeypatch.setenv("SCCFM_CONFIG", str(path))
    return path


@pytest.fixture
def default_config(config_path: Path) -> Config:
    """Creates and saves a default test configuration."""
    config = Config(profile="default", region="us", api_token="tok12345")
    ConfigService(path=config_path).save(config)
    return config


@pytest.fixture
def mock_inventory_service(monkeypatch: MonkeyPatch) -> None:
    """Mocks InventoryService __init__ to avoid API calls."""

    def stub_init(self: InventoryService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "__init__", stub_init)


@pytest.fixture
def sample_devices() -> list[Device]:
    """Provides sample device objects for testing."""
    return [
        Device(
            uid="uid-1",
            name="perimeter-fw",
            device_type=EntityType.GENERIC_DEVICE,
            software_version="1.0.0",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
        Device(
            uid="uid-2",
            name="edge-nva",
            device_type=EntityType.ASA,
            software_version="1.0.0",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
    ]


@pytest.fixture
def sample_managers() -> list[Device]:
    """Provides sample manager objects for testing."""
    return [
        Device(
            uid="uid-1",
            name="us-east-manager",
            device_type=EntityType.ONPREM_FMC,
            software_version="3.0.0",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
        Device(
            uid="uid-2",
            name="eu-central-manager",
            device_type=EntityType.ONPREM_FMC,
            software_version="3.0.0",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
    ]


@pytest.fixture
def sample_cli_results() -> list[CdoCliResult]:
    """Provides sample CLI execution results for testing."""
    return [
        CdoCliResult(
            uid="uid-3",
            device_uid="uid-1",
            result="Cisco Adaptive Security Appliance Software Version 9.16.1",
            error_msg=None,
        ),
        CdoCliResult(
            uid="uid-122",
            device_uid="uid-2",
            result="Cisco Adaptive Security Appliance Software Version 9.18.2",
            error_msg=None,
        ),
    ]

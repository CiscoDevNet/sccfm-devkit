# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml
from plugins.modules import register_cdfmc_ftd  # noqa: E402
from scc_firewall_manager_sdk import ConfigState, ConnectivityState, Device, EntityType


@pytest.fixture
def sample_device() -> Device:
    return Device(
        uid="cdfmc-ftd-uid-123",
        name="test-cdfmc-ftd-01",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        softwareVersion="7.4.1",
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    return {
        "ftd_uid": "cdfmc-ftd-uid-123",
        "skip_initial_deployment": False,
        "profile": "default",
    }


@pytest.fixture
def mock_module_instance(base_module_params: dict[str, Any]) -> MagicMock:
    mock_module = MagicMock()
    mock_module.params = base_module_params.copy()
    mock_module.check_mode = False
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


def test_module_is_in_all_action_group() -> None:
    runtime_path = Path(__file__).parents[3] / "meta" / "runtime.yml"
    runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))

    assert "register_cdfmc_ftd" in runtime["action_groups"]["cisco.sccfm.all"]


@patch("plugins.modules.register_cdfmc_ftd.Config")
@patch("plugins.modules.register_cdfmc_ftd.FtdRegisterService")
@patch("plugins.modules.register_cdfmc_ftd.AnsibleModule")
def test_should_register_ftd_and_return_device(
    mock_ansible_module_class: MagicMock,
    mock_register_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_device: Device,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    mock_register = MagicMock()
    mock_register.register_ftd.return_value = sample_device
    mock_register_service_class.return_value = mock_register

    with pytest.raises(SystemExit):
        register_cdfmc_ftd.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["device"]["uid"] == "cdfmc-ftd-uid-123"
    mock_register.register_ftd.assert_called_once_with(
        ftd_uid="cdfmc-ftd-uid-123",
        skip_initial_deployment=False,
    )


@patch("plugins.modules.register_cdfmc_ftd.Config")
@patch("plugins.modules.register_cdfmc_ftd.AnsibleModule")
def test_check_mode_returns_empty_device(
    mock_ansible_module_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    with pytest.raises(SystemExit):
        register_cdfmc_ftd.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["device"] == {}

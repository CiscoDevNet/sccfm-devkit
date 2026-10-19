# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import configure_manager

from cisco_sccfm_core.services.inventory import ConfigureManagerResult, FtdConfigureManagerError

_CLI_KEY = "configure manager add fmc.example.com regkey123 natid456"


@pytest.fixture
def base_params() -> dict[str, Any]:
    return {
        "ftd_host": "203.0.113.10",
        "ftd_port": 22,
        "ftd_user": "admin",
        "ftd_password": "s3cr3t",
        "cli_key": _CLI_KEY,
        "jump_host": None,
        "jump_password": None,
        "ssh_timeout": 30,
    }


@pytest.fixture
def mock_module(base_params: dict[str, Any]) -> MagicMock:
    module = MagicMock()
    module.params = base_params.copy()
    module.check_mode = False
    module.exit_json.side_effect = SystemExit(0)
    module.fail_json.side_effect = SystemExit(1)
    return module


@patch("plugins.modules.configure_manager.FtdConfigureManagerService")
@patch("plugins.modules.configure_manager.AnsibleModule")
def test_should_configure_manager(
    mock_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module_class.return_value = mock_module

    service = MagicMock()
    service.configure_manager.return_value = ConfigureManagerResult(
        host="203.0.113.10",
        success=True,
        output="Manager fmc.example.com successfully configured.",
        message="Manager successfully configured.",
    )
    mock_service_class.return_value = service

    with pytest.raises(SystemExit):
        configure_manager.run_module()

    service.configure_manager.assert_called_once()
    call_kwargs = service.configure_manager.call_args[1]
    assert call_kwargs["host"] == "203.0.113.10"
    assert call_kwargs["username"] == "admin"
    assert call_kwargs["password"] == "s3cr3t"
    assert call_kwargs["cli_key"] == _CLI_KEY
    assert call_kwargs["jump"] is None

    mock_module.exit_json.assert_called_once()
    exit_kwargs = mock_module.exit_json.call_args[1]
    assert exit_kwargs["changed"] is True
    assert exit_kwargs["success"] is True
    assert exit_kwargs["host"] == "203.0.113.10"


@patch("plugins.modules.configure_manager.FtdConfigureManagerService")
@patch("plugins.modules.configure_manager.AnsibleModule")
def test_should_forward_jump_host(
    mock_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["jump_host"] = "bastion@203.0.113.5:2222"
    mock_module.params["jump_password"] = "jump-pw"
    mock_module_class.return_value = mock_module

    service = MagicMock()
    service.configure_manager.return_value = ConfigureManagerResult(
        host="203.0.113.10", success=True, output="", message="ok"
    )
    mock_service_class.return_value = service

    with pytest.raises(SystemExit):
        configure_manager.run_module()

    jump = service.configure_manager.call_args[1]["jump"]
    assert jump is not None
    assert jump.host == "203.0.113.5"
    assert jump.port == 2222
    assert jump.username == "bastion"
    assert jump.password == "jump-pw"


@patch("plugins.modules.configure_manager.FtdConfigureManagerService")
@patch("plugins.modules.configure_manager.AnsibleModule")
def test_should_fail_on_malformed_jump_host(
    mock_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["jump_host"] = "host:99999"
    mock_module_class.return_value = mock_module

    with pytest.raises(SystemExit):
        configure_manager.run_module()

    mock_service_class.assert_not_called()
    mock_module.fail_json.assert_called_once()
    assert "port" in mock_module.fail_json.call_args[1]["msg"].casefold()


@patch("plugins.modules.configure_manager.FtdConfigureManagerService")
@patch("plugins.modules.configure_manager.AnsibleModule")
def test_should_fail_when_password_missing(
    mock_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["ftd_password"] = None
    mock_module_class.return_value = mock_module

    with pytest.raises(SystemExit):
        configure_manager.run_module()

    mock_service_class.assert_not_called()
    mock_module.fail_json.assert_called_once()
    assert "ftd_password is required" in mock_module.fail_json.call_args[1]["msg"]


@patch("plugins.modules.configure_manager.FtdConfigureManagerService")
@patch("plugins.modules.configure_manager.AnsibleModule")
def test_should_fail_when_ftd_rejects(
    mock_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module_class.return_value = mock_module

    service = MagicMock()
    service.configure_manager.side_effect = FtdConfigureManagerError(
        "FTD did not confirm manager configuration on 203.0.113.10.",
        output="Manager already configured.",
    )
    mock_service_class.return_value = service

    with pytest.raises(SystemExit):
        configure_manager.run_module()

    mock_module.fail_json.assert_called_once()
    fail_kwargs = mock_module.fail_json.call_args[1]
    assert "did not confirm" in fail_kwargs["msg"]
    assert fail_kwargs["output"] == "Manager already configured."
    assert fail_kwargs["success"] is False


@patch("plugins.modules.configure_manager.FtdConfigureManagerService")
@patch("plugins.modules.configure_manager.AnsibleModule")
def test_should_fail_on_invalid_cli_key(
    mock_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module_class.return_value = mock_module

    service = MagicMock()
    service.configure_manager.side_effect = ValueError(
        "The --cli-key must start with 'configure manager add'."
    )
    mock_service_class.return_value = service

    with pytest.raises(SystemExit):
        configure_manager.run_module()

    mock_module.fail_json.assert_called_once()
    assert "configure manager add" in mock_module.fail_json.call_args[1]["msg"]


@patch("plugins.modules.configure_manager.FtdConfigureManagerService")
@patch("plugins.modules.configure_manager.AnsibleModule")
def test_should_support_check_mode_without_ssh(
    mock_module_class: MagicMock,
    mock_service_class: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.check_mode = True
    mock_module_class.return_value = mock_module

    with pytest.raises(SystemExit):
        configure_manager.run_module()

    mock_service_class.assert_not_called()
    mock_module.exit_json.assert_called_once()
    exit_kwargs = mock_module.exit_json.call_args[1]
    assert exit_kwargs["changed"] is True
    assert "success" not in exit_kwargs
    assert "Would configure manager" in exit_kwargs["msg"]

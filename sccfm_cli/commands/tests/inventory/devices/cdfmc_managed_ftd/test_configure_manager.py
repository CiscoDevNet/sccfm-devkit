# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for ``sccfm_cli inventory devices cdfmc-managed-ftd configure-manager``."""

from __future__ import annotations

import json
import socket
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services.inventory import (
    ConfigureManagerResult,
    FtdConfigureManagerError,
    FtdConfigureManagerService,
    ReachabilityResult,
)

_CLI_KEY = "configure manager add DONTRESOLVE regkey123 natid456"

_BASE_ARGS = [
    "inventory",
    "devices",
    "cdfmc-managed-ftd",
    "configure-manager",
    "--ftd-host",
    "10.0.0.5",
    "--ftd-user",
    "admin",
    "--ftd-password",
    "s3cr3t",
    "--cli-key",
    _CLI_KEY,
]


def _stub_service_init(self: FtdConfigureManagerService, config: Any = None) -> None:
    return None


class TestSuccessfulConfigure:
    def test_should_configure_and_report_table(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)

        captured: dict[str, Any] = {}

        def fake_configure(
            self: FtdConfigureManagerService, **kwargs: Any
        ) -> ConfigureManagerResult:
            captured.update(kwargs)
            return ConfigureManagerResult(
                host=kwargs["host"],
                success=True,
                output="Manager successfully configured.",
                message="Manager successfully configured.",
            )

        monkeypatch.setattr(FtdConfigureManagerService, "configure_manager", fake_configure)

        result = cli_runner.invoke(cli, _BASE_ARGS + ["--format", "table"])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "10.0.0.5" in result.output
        assert "successfully configured" in result.output.casefold()
        assert captured["cli_key"] == _CLI_KEY
        assert captured["host"] == "10.0.0.5"
        assert captured["username"] == "admin"
        assert captured["port"] == 22

    def test_should_configure_and_report_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)
        monkeypatch.setattr(
            FtdConfigureManagerService,
            "configure_manager",
            lambda self, **kwargs: ConfigureManagerResult(
                host=kwargs["host"],
                success=True,
                output="Manager successfully configured.",
                message="Manager successfully configured.",
            ),
        )

        result = cli_runner.invoke(cli, _BASE_ARGS + ["--format", "json"])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output)
        assert payload["success"] is True
        assert payload["host"] == "10.0.0.5"

    def test_should_read_password_from_env(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SCCFM_FTD_PASSWORD", "from-env")
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)

        captured: dict[str, Any] = {}

        def fake_configure(
            self: FtdConfigureManagerService, **kwargs: Any
        ) -> ConfigureManagerResult:
            captured.update(kwargs)
            return ConfigureManagerResult(
                host=kwargs["host"], success=True, output="", message="ok"
            )

        monkeypatch.setattr(FtdConfigureManagerService, "configure_manager", fake_configure)

        args = [
            "inventory",
            "devices",
            "cdfmc-managed-ftd",
            "configure-manager",
            "--ftd-host",
            "10.0.0.5",
            "--ftd-user",
            "admin",
            "--cli-key",
            _CLI_KEY,
        ]
        result = cli_runner.invoke(cli, args)

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured["password"] == "from-env"

    def test_should_read_cli_key_from_env(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SCCFM_FTD_CLI_KEY", _CLI_KEY)
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)

        captured: dict[str, Any] = {}

        def fake_configure(
            self: FtdConfigureManagerService, **kwargs: Any
        ) -> ConfigureManagerResult:
            captured.update(kwargs)
            return ConfigureManagerResult(
                host=kwargs["host"], success=True, output="", message="ok"
            )

        monkeypatch.setattr(FtdConfigureManagerService, "configure_manager", fake_configure)
        args = [
            "inventory",
            "devices",
            "cdfmc-managed-ftd",
            "configure-manager",
            "--ftd-host",
            "10.0.0.5",
            "--ftd-user",
            "admin",
            "--ftd-password",
            "password",
        ]

        result = cli_runner.invoke(cli, args)

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured["cli_key"] == _CLI_KEY


class TestFailure:
    def test_should_fail_when_ftd_rejects(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)

        def fake_configure(
            self: FtdConfigureManagerService, **kwargs: Any
        ) -> ConfigureManagerResult:
            raise FtdConfigureManagerError(
                "FTD did not confirm manager configuration on 10.0.0.5.",
                output="Manager already configured.",
            )

        monkeypatch.setattr(FtdConfigureManagerService, "configure_manager", fake_configure)

        result = cli_runner.invoke(cli, _BASE_ARGS)

        assert result.exit_code != 0
        assert "did not confirm" in result.output
        assert "Manager already configured." in result.output

    def test_should_fail_on_invalid_cli_key(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)

        def fake_configure(
            self: FtdConfigureManagerService, **kwargs: Any
        ) -> ConfigureManagerResult:
            raise ValueError("The --cli-key must start with 'configure manager add'.")

        monkeypatch.setattr(FtdConfigureManagerService, "configure_manager", fake_configure)

        result = cli_runner.invoke(
            cli,
            _BASE_ARGS[:-1] + ["show version"],
        )

        assert result.exit_code != 0
        assert "configure manager add" in result.output


class TestCheckMode:
    def test_check_reachable(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        class _FakeConn:
            def __enter__(self) -> _FakeConn:
                return self

            def __exit__(self, *args: Any) -> None:
                return None

        monkeypatch.setattr(socket, "create_connection", lambda *a, **k: _FakeConn())

        result = cli_runner.invoke(cli, _BASE_ARGS + ["--check"])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "reachable" in result.output

    def test_check_unreachable_exits_nonzero(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def _raise(*args: Any, **kwargs: Any) -> None:
            raise OSError("connection refused")

        monkeypatch.setattr(socket, "create_connection", _raise)

        result = cli_runner.invoke(cli, _BASE_ARGS + ["--check"])

        assert result.exit_code != 0
        assert "not reachable" in result.output

    def test_check_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def _raise(*args: Any, **kwargs: Any) -> None:
            raise OSError("connection refused")

        monkeypatch.setattr(socket, "create_connection", _raise)

        result = cli_runner.invoke(cli, _BASE_ARGS + ["--check", "--format", "json"])

        assert result.exit_code != 0
        # JSON status line is printed before the error exit.
        assert '"reachable": false' in result.output


class TestJumpHost:
    def test_should_forward_jump_host(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SCCFM_JUMP_PASSWORD", "jump-pw")
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)

        captured: dict[str, Any] = {}

        def fake_configure(
            self: FtdConfigureManagerService, **kwargs: Any
        ) -> ConfigureManagerResult:
            captured.update(kwargs)
            return ConfigureManagerResult(
                host=kwargs["host"], success=True, output="", message="ok"
            )

        monkeypatch.setattr(FtdConfigureManagerService, "configure_manager", fake_configure)

        result = cli_runner.invoke(
            cli,
            _BASE_ARGS + ["--jump-host", "bastion@203.0.113.5:2222"],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        jump = captured["jump"]
        assert jump is not None
        assert jump.host == "203.0.113.5"
        assert jump.port == 2222
        assert jump.username == "bastion"
        assert jump.password == "jump-pw"

    def test_should_fail_on_malformed_jump_host(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)

        result = cli_runner.invoke(
            cli,
            _BASE_ARGS + ["--jump-host", "host:99999"],
        )

        assert result.exit_code != 0
        assert "port" in result.output.casefold()

    def test_no_jump_host_passes_none(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)

        captured: dict[str, Any] = {}

        def fake_configure(
            self: FtdConfigureManagerService, **kwargs: Any
        ) -> ConfigureManagerResult:
            captured.update(kwargs)
            return ConfigureManagerResult(
                host=kwargs["host"], success=True, output="", message="ok"
            )

        monkeypatch.setattr(FtdConfigureManagerService, "configure_manager", fake_configure)

        result = cli_runner.invoke(cli, _BASE_ARGS)

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured["jump"] is None

    def test_should_prompt_for_jump_password(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)

        captured: dict[str, Any] = {}

        def fake_configure(
            self: FtdConfigureManagerService, **kwargs: Any
        ) -> ConfigureManagerResult:
            captured.update(kwargs)
            return ConfigureManagerResult(
                host=kwargs["host"], success=True, output="", message="ok"
            )

        monkeypatch.setattr(FtdConfigureManagerService, "configure_manager", fake_configure)

        # No --jump-password and no env var → prompted. Provide it via stdin.
        result = cli_runner.invoke(
            cli,
            _BASE_ARGS + ["--jump-host", "bastion@203.0.113.5:2222"],
            input="prompted-jump-pw\n",
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured["jump"].password == "prompted-jump-pw"

    def test_blank_jump_password_prompt_means_key_auth(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)

        captured: dict[str, Any] = {}

        def fake_configure(
            self: FtdConfigureManagerService, **kwargs: Any
        ) -> ConfigureManagerResult:
            captured.update(kwargs)
            return ConfigureManagerResult(
                host=kwargs["host"], success=True, output="", message="ok"
            )

        monkeypatch.setattr(FtdConfigureManagerService, "configure_manager", fake_configure)

        # Blank line at the prompt → no password → key/agent auth.
        result = cli_runner.invoke(
            cli,
            _BASE_ARGS + ["--jump-host", "bastion@203.0.113.5:2222"],
            input="\n",
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured["jump"].password is None


class TestFtdPasswordPrompt:
    def test_should_prompt_when_password_omitted(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)

        captured: dict[str, Any] = {}

        def fake_configure(
            self: FtdConfigureManagerService, **kwargs: Any
        ) -> ConfigureManagerResult:
            captured.update(kwargs)
            return ConfigureManagerResult(
                host=kwargs["host"], success=True, output="", message="ok"
            )

        monkeypatch.setattr(FtdConfigureManagerService, "configure_manager", fake_configure)

        # Drop the --ftd-password pair from the base args; expect a prompt.
        args = [a for a in _BASE_ARGS if a not in ("--ftd-password", "s3cr3t")]
        result = cli_runner.invoke(cli, args, input="prompted-ftd-pw\n")

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured["password"] == "prompted-ftd-pw"

    def test_should_fail_when_password_omitted_non_interactive(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)

        # No --ftd-password, no env var, and no TTY (CliRunner stdin is not a tty):
        # must fail cleanly instead of aborting at a hidden prompt.
        args = [a for a in _BASE_ARGS if a not in ("--ftd-password", "s3cr3t")]
        result = cli_runner.invoke(cli, args, input="")

        assert result.exit_code != 0
        assert "password is required" in result.output

    def test_should_use_empty_string_password_as_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)

        # An explicitly empty password is treated as "not provided": non-interactive
        # so it should fail rather than silently SSHing with an empty password.
        args = [a if a != "s3cr3t" else "" for a in _BASE_ARGS]
        result = cli_runner.invoke(cli, args, input="")

        assert result.exit_code != 0
        assert "password is required" in result.output

    def test_check_does_not_prompt_for_password(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(FtdConfigureManagerService, "__init__", _stub_service_init)
        monkeypatch.setattr(
            FtdConfigureManagerService,
            "check_reachable",
            lambda self, **kwargs: ReachabilityResult(
                host=kwargs["host"], port=kwargs["port"], reachable=True, detail="ok"
            ),
        )

        # No --ftd-password, no env var, no stdin. Must not hang/prompt.
        args = [a for a in _BASE_ARGS if a not in ("--ftd-password", "s3cr3t")]
        result = cli_runner.invoke(cli, args + ["--check"], input="")

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "reachable" in result.output

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from dataclasses import replace
from typing import Any, Sequence, cast

import click
from rich.console import Console

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.inventory.options import format_option
from cisco_sccfm_cli.utils import print_json, with_spinner
from cisco_sccfm_core.services.inventory import (
    FtdConfigureManagerError,
    FtdConfigureManagerService,
    JumpHostSpec,
    parse_jump_host,
)


class FtdConfigureManagerCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)

    @property
    def name(self) -> str:
        return "configure-manager"

    @property
    def help_text(self) -> str:
        return (
            "Complete cdFMC-managed FTD onboarding by SSHing into the FTD VM and running "
            "the 'configure manager add ...' command produced by 'onboard'. "
            "Only works if the FTD is reachable on its SSH port (--ftd-port, default 22) "
            "from this host, or from the jump host when --jump-host is set."
        )

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["--ftd-host"],
                required=True,
                help="Management IP address or hostname of the FTD VM.",
            ),
            click.Option(
                ["--ftd-port"],
                type=click.IntRange(min=1, max=65535),
                default=22,
                show_default=True,
                help="SSH port of the FTD VM.",
            ),
            click.Option(
                ["--ftd-user"],
                required=True,
                help="SSH username for the FTD VM.",
            ),
            click.Option(
                ["--ftd-password"],
                default=None,
                envvar="SCCFM_FTD_PASSWORD",
                help="SSH password for the FTD VM (or set SCCFM_FTD_PASSWORD; prompted if needed).",
            ),
            click.Option(
                ["--cli-key"],
                required=True,
                envvar="SCCFM_FTD_CLI_KEY",
                help=(
                    "The full 'configure manager add ...' string returned by 'onboard' "
                    "(or set SCCFM_FTD_CLI_KEY)."
                ),
            ),
            click.Option(
                ["--jump-host"],
                default=None,
                help=(
                    "Optional bastion to tunnel through, as [user@]host[:port]. "
                    "The FTD then sees the connection from the jump host's IP, so that "
                    "IP must be on the FTD ssh-access-list."
                ),
            ),
            click.Option(
                ["--jump-password"],
                default=None,
                envvar="SCCFM_JUMP_PASSWORD",
                help=(
                    "Password for the jump host (or set SCCFM_JUMP_PASSWORD). "
                    "Prompted if omitted; leave blank to use SSH key/agent auth."
                ),
            ),
            click.Option(
                ["--ssh-timeout"],
                type=click.IntRange(min=1),
                default=30,
                show_default=True,
                help="SSH connect and read timeout in seconds.",
            ),
            click.Option(
                ["--check"],
                is_flag=True,
                default=False,
                help="Only verify reachability of the FTD SSH port; do not send the command.",
            ),
            format_option(),
        ]

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        host = cast(str, kwargs.get("ftd_host"))
        port = cast(int, kwargs.get("ftd_port", 22))
        timeout = cast(int, kwargs.get("ssh_timeout", 30))
        output_format = cast(str, kwargs.get("format"))
        check = cast(bool, kwargs.get("check", False))

        # Resolve credentials before the spinner starts; prompting under a live
        # spinner garbles the terminal.
        jump = self._build_jump_spec(**kwargs)
        password = "" if check else self._resolve_ftd_password(**kwargs)

        # This command talks to the device purely over SSH and never calls the
        # SCCFM API, so it deliberately does not require a configured profile.
        service = FtdConfigureManagerService()

        if check:
            self._handle_check(service, host, port, timeout, output_format, jump)
            return

        self._execute(service, host, port, timeout, output_format, jump, password, **kwargs)

    @with_spinner("Configuring manager on FTD via SSH...")
    def _execute(
        self,
        service: FtdConfigureManagerService,
        host: str,
        port: int,
        timeout: int,
        output_format: str,
        jump: JumpHostSpec | None,
        password: str,
        **kwargs: Any,
    ) -> None:
        username = cast(str, kwargs.get("ftd_user"))
        cli_key = cast(str, kwargs.get("cli_key"))
        try:
            result = service.configure_manager(
                host=host,
                port=port,
                username=username,
                password=password,
                cli_key=cli_key,
                timeout=timeout,
                jump=jump,
            )
        except ValueError as exc:
            raise click.ClickException(str(exc))
        except FtdConfigureManagerError as exc:
            if exc.output:
                raise click.ClickException(f"{exc}\nDevice output:\n{exc.output}")
            raise click.ClickException(str(exc))

        if output_format == "json":
            print_json(result.to_dict())
        else:
            self.console.print(f"[green]✓[/green] {host}: {result.message}")

    def _resolve_ftd_password(self, **kwargs: Any) -> str:
        # Treat an empty string the same as missing, so SCCFM_FTD_PASSWORD="" or
        # --ftd-password "" does not silently SSH with a blank password.
        password = cast("str | None", kwargs.get("ftd_password"))
        if password:
            return password
        try:
            return cast(str, click.prompt("FTD password", hide_input=True))
        except click.Abort:
            # click.prompt raises Abort for both Ctrl-C and EOF. On a real
            # terminal it's an intentional Ctrl-C, so let it propagate to the
            # standard interrupt handling. Without a tty (CI / piped stdin) it's
            # EOF on the hidden prompt, so fail with a clear message instead.
            if sys.stdin.isatty():
                raise
            raise click.ClickException(
                "FTD password is required. Provide --ftd-password or set "
                "SCCFM_FTD_PASSWORD when running non-interactively."
            )

    def _build_jump_spec(self, **kwargs: Any) -> JumpHostSpec | None:
        jump_host = cast("str | None", kwargs.get("jump_host"))
        if not jump_host:
            return None
        # Validate the host string before prompting, so malformed input fails fast
        # rather than asking for a password we'd then discard.
        try:
            spec = parse_jump_host(jump_host, None)
        except ValueError as exc:
            raise click.ClickException(str(exc))

        jump_password = cast("str | None", kwargs.get("jump_password"))
        if jump_password is None:
            jump_password = click.prompt(
                "Jump host password (leave blank for key/agent auth)",
                hide_input=True,
                default="",
                show_default=False,
            )
        # An empty string means "no password — use key/agent"; normalise to None.
        return replace(spec, password=jump_password or None)

    def _handle_check(
        self,
        service: FtdConfigureManagerService,
        host: str,
        port: int,
        timeout: int,
        output_format: str,
        jump: JumpHostSpec | None,
    ) -> None:
        result = service.check_reachable(host=host, port=port, timeout=timeout, jump=jump)

        if output_format == "json":
            print_json(result.to_dict())
        elif result.reachable:
            self.console.print(f"[green]✓[/green] {host}:{port} is reachable. {result.detail}")
        else:
            self.console.print(f"[red]✗[/red] {host}:{port} — {result.detail}")

        if not result.reachable:
            raise click.ClickException(f"FTD {host}:{port} is not reachable.")

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import getpass
import re
import socket
import time
from dataclasses import dataclass

import paramiko

from sccfm_core.types import ConfigLike

_PROMPT = ">"
# The FTD confirms with a line like "Manager <fmc-host> successfully configured."
# Match per line (not across the whole buffer): the interactive shell echoes the
# typed "configure manager add ..." command back, so a buffer-wide search would
# latch the echoed "manager" onto an unrelated later "successfully configured"
# (e.g. "DNS successfully configured"). Requiring the marker on a line that
# starts with "manager" also lets the FMC host contain "not" (e.g. "not-prod").
_SUCCESS_LINE = re.compile(r"^manager\b.*\bsuccessfully configured\b", re.IGNORECASE)
_NEGATED = re.compile(r"\bnot successfully configured\b", re.IGNORECASE)
_RECV_CHUNK = 4096


class FtdConfigureManagerError(Exception):
    """Raised when the FTD rejects the command or the SSH session fails.

    Carries the raw device output (when available) so callers can surface it.
    """

    def __init__(self, message: str, output: str = "") -> None:
        super().__init__(message)
        self.output = output


@dataclass(frozen=True)
class ConfigureManagerResult:
    """Outcome of running a ``configure manager add`` command over SSH.

    The output field contains device output with the echoed registration command removed.
    """

    host: str
    success: bool
    output: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "host": self.host,
            "success": self.success,
            "output": self.output,
            "message": self.message,
        }


@dataclass(frozen=True)
class JumpHostSpec:
    """Connection details for a bastion/jump host fronting the FTD."""

    host: str
    port: int
    username: str
    password: str | None

    def label(self) -> str:
        return f"{self.username}@{self.host}:{self.port}"


@dataclass(frozen=True)
class ReachabilityResult:
    """Outcome of a reachability probe to the FTD SSH port."""

    host: str
    port: int
    reachable: bool
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "reachable": self.reachable,
            "detail": self.detail,
        }


class FtdConfigureManagerService:
    """Complete cdFMC-managed FTD onboarding by pasting the registration command.

    SSHes into the FTD VM's interactive CLI and runs the
    ``configure manager add ...`` string returned by the onboard command.
    """

    def __init__(self, config: ConfigLike | None = None) -> None:
        # This service talks to the device purely over SSH and never calls the
        # SCCFM API, so config is accepted for interface parity but unused.
        self._config = config

    def configure_manager(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        cli_key: str,
        timeout: int,
        jump: JumpHostSpec | None = None,
    ) -> ConfigureManagerResult:
        command = _validate_cli_key(cli_key)

        jump_client, sock = self._open_jump_channel(jump, host, port, timeout)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            try:
                client.connect(
                    hostname=host,
                    port=port,
                    username=username,
                    password=password,
                    timeout=timeout,
                    look_for_keys=False,
                    allow_agent=False,
                    sock=sock,
                )
            except paramiko.AuthenticationException as exc:
                raise FtdConfigureManagerError(
                    f"SSH authentication failed for {username}@{host}:{port}."
                ) from exc
            except (paramiko.SSHException, socket.timeout, OSError) as exc:
                raise FtdConfigureManagerError(
                    f"Could not establish SSH connection to {host}:{port}: {exc}"
                ) from exc

            try:
                channel = client.invoke_shell()
                channel.settimeout(timeout)
                # Drain the banner / wait for the initial '>' prompt.
                _read_until_prompt(channel, timeout)
                channel.send(command + "\n")
                output = _read_until_prompt(channel, timeout)
            except FtdConfigureManagerError as exc:
                raise FtdConfigureManagerError(
                    str(exc),
                    output=_sanitize_manager_command_echo(exc.output, command),
                ) from exc
            except (paramiko.SSHException, socket.timeout, OSError) as exc:
                raise FtdConfigureManagerError(
                    f"SSH session error while configuring manager on {host}: {exc}"
                ) from exc
        finally:
            client.close()
            if jump_client is not None:
                jump_client.close()

        sanitized_output = _sanitize_manager_command_echo(output, command)
        if not _is_success(output):
            raise FtdConfigureManagerError(
                f"FTD did not confirm manager configuration on {host}.",
                output=sanitized_output,
            )

        return ConfigureManagerResult(
            host=host,
            success=True,
            output=sanitized_output,
            message="Manager successfully configured.",
        )

    def check_reachable(
        self,
        *,
        host: str,
        port: int,
        timeout: int,
        jump: JumpHostSpec | None = None,
    ) -> ReachabilityResult:
        """Probe whether the FTD SSH port is reachable, optionally via a jump host.

        Without a jump host this is a direct TCP connect. With one, it opens the
        bastion channel to the FTD (which is the only path that can work when the
        FTD is not directly routable).
        """
        if jump is None:
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    pass
            except OSError as exc:
                return ReachabilityResult(host, port, False, f"TCP connection failed: {exc}")
            return ReachabilityResult(host, port, True, "TCP connection succeeded.")

        jump_client = None
        try:
            jump_client, _sock = self._open_jump_channel(jump, host, port, timeout)
        except FtdConfigureManagerError as exc:
            return ReachabilityResult(host, port, False, str(exc))
        finally:
            if jump_client is not None:
                jump_client.close()
        return ReachabilityResult(host, port, True, f"Reachable via jump host {jump.label()}.")

    def _open_jump_channel(
        self,
        jump: JumpHostSpec | None,
        ftd_host: str,
        ftd_port: int,
        timeout: int,
    ) -> tuple[paramiko.SSHClient | None, paramiko.Channel | None]:
        """Connect to the jump host and open a direct-tcpip channel to the FTD.

        Returns ``(None, None)`` when no jump host is configured so the caller
        connects to the FTD directly. Otherwise returns the live jump client
        (which must stay open for the duration of the FTD session) and the
        channel to pass as ``sock=`` to the FTD connect.
        """
        if jump is None:
            return None, None

        jump_client = paramiko.SSHClient()
        jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            jump_client.connect(
                hostname=jump.host,
                port=jump.port,
                username=jump.username,
                password=jump.password or None,
                timeout=timeout,
                look_for_keys=True,
                allow_agent=True,
            )
        except paramiko.AuthenticationException as exc:
            jump_client.close()
            raise FtdConfigureManagerError(
                f"SSH authentication failed for jump host {jump.label()}."
            ) from exc
        except (paramiko.SSHException, socket.timeout, OSError) as exc:
            jump_client.close()
            raise FtdConfigureManagerError(
                f"Could not connect to jump host {jump.label()}: {exc}"
            ) from exc

        try:
            transport = jump_client.get_transport()
            channel = transport.open_channel("direct-tcpip", (ftd_host, ftd_port), ("", 0))
        except (paramiko.SSHException, OSError) as exc:
            jump_client.close()
            raise FtdConfigureManagerError(
                f"Jump host {jump.label()} could not reach {ftd_host}:{ftd_port}: {exc}"
            ) from exc

        return jump_client, channel


def parse_jump_host(value: str, password: str | None, default_port: int = 22) -> JumpHostSpec:
    """Parse a ``[user@]host[:port]`` jump-host string into a :class:`JumpHostSpec`.

    Falls back to the current OS user when no ``user@`` is given.
    """
    spec = value.strip()
    if not spec:
        raise ValueError("--jump-host must not be empty.")

    username = getpass.getuser()
    if "@" in spec:
        username, _, spec = spec.partition("@")
        if not username or not spec:
            raise ValueError("--jump-host must be in the form [user@]host[:port].")

    port = default_port
    if ":" in spec:
        spec, _, port_str = spec.partition(":")
        if not port_str.isdigit() or not 1 <= int(port_str) <= 65535:
            raise ValueError(f"Invalid jump-host port: '{port_str}'.")
        port = int(port_str)

    if not spec:
        raise ValueError("--jump-host must include a host.")

    return JumpHostSpec(host=spec, port=port, username=username, password=password)


def _is_success(output: str) -> bool:
    """Return True if any line confirms the manager was configured.

    Matches per line so the echoed command and unrelated sub-status lines
    (e.g. "DNS successfully configured") cannot trigger a false positive.
    """
    for line in output.splitlines():
        stripped = line.strip()
        if _SUCCESS_LINE.match(stripped) and not _NEGATED.search(stripped):
            return True
    return False


def _validate_cli_key(cli_key: str) -> str:
    normalized = cli_key.strip()
    if not normalized:
        raise ValueError("A non-empty --cli-key is required.")
    if "\n" in normalized or "\r" in normalized:
        raise ValueError("The --cli-key must be a single line.")
    if not normalized.casefold().startswith("configure manager add"):
        raise ValueError("The --cli-key must start with 'configure manager add'.")
    return normalized


def _sanitize_manager_command_echo(output: str, command: str) -> str:
    command_marker = command.casefold()
    sanitized_lines: list[str] = []
    for line in output.splitlines():
        if command_marker in line.strip().casefold():
            continue
        sanitized_lines.append(line)
    return "\n".join(sanitized_lines).strip()


def _read_until_prompt(channel: paramiko.Channel, timeout: int) -> str:
    """Accumulate channel output until the FTD prompt reappears or time runs out."""
    deadline = time.time() + timeout
    buffer = ""
    while True:
        if channel.recv_ready():
            chunk: str = channel.recv(_RECV_CHUNK).decode(errors="replace")
            if chunk:
                buffer += chunk
                # Only stop when the prompt occupies its own line, so a banner or
                # EULA line that merely ends in '>' (e.g. "... read the EULA -->")
                # doesn't end the read before the real CLI prompt appears.
                last_line = buffer.rstrip().rsplit("\n", 1)[-1].strip()
                if last_line == _PROMPT:
                    return buffer
        if time.time() >= deadline:
            raise FtdConfigureManagerError(
                "Timed out waiting for the FTD CLI prompt.",
                output=buffer.strip(),
            )
        time.sleep(0.1)

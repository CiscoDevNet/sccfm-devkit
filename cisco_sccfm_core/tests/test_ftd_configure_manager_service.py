# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for :class:`FtdConfigureManagerService`."""

from __future__ import annotations

from typing import Any

import paramiko
import pytest
from _pytest.monkeypatch import MonkeyPatch

from cisco_sccfm_core.services.inventory import (
    FtdConfigureManagerError,
    FtdConfigureManagerService,
    JumpHostSpec,
)
from cisco_sccfm_core.services.inventory import ftd_configure_manager_service as svc_mod
from cisco_sccfm_core.services.inventory import parse_jump_host

_CLI_KEY = "configure manager add DONTRESOLVE regkey123 natid456"
_SUCCESS_CHUNKS = [b"\r\n> ", b"Manager successfully configured.\r\n> "]


class _FakeChannel:
    """Minimal paramiko channel stub that replays scripted output chunks."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)
        self.sent: list[str] = []

    def settimeout(self, _timeout: float) -> None:
        return None

    def recv_ready(self) -> bool:
        return bool(self._chunks)

    def recv(self, _n: int) -> bytes:
        return self._chunks.pop(0)

    def send(self, data: str) -> int:
        self.sent.append(data)
        return len(data)


class _FakeClient:
    def __init__(self, channel: _FakeChannel) -> None:
        self._channel = channel
        self.closed = False
        self.connect_kwargs: dict[str, Any] = {}

    def set_missing_host_key_policy(self, _policy: Any) -> None:
        return None

    def connect(self, **kwargs: Any) -> None:
        self.connect_kwargs = kwargs

    def invoke_shell(self) -> _FakeChannel:
        return self._channel

    def close(self) -> None:
        self.closed = True


def _patch_client(monkeypatch: MonkeyPatch, client: _FakeClient) -> None:
    monkeypatch.setattr(svc_mod.paramiko, "SSHClient", lambda: client)


def _service() -> FtdConfigureManagerService:
    return FtdConfigureManagerService(config=object())


def test_success_parses_confirmation(monkeypatch: MonkeyPatch) -> None:
    channel = _FakeChannel(
        [
            b"\r\n> ",  # initial prompt
            b"Manager successfully configured.\r\n> ",  # after command
        ]
    )
    client = _FakeClient(channel)
    _patch_client(monkeypatch, client)

    result = _service().configure_manager(
        host="10.0.0.5",
        port=22,
        username="admin",
        password="pw",
        cli_key=_CLI_KEY,
        timeout=5,
    )

    assert result.success is True
    assert result.host == "10.0.0.5"
    assert "successfully configured" in result.output.casefold()
    assert channel.sent == [_CLI_KEY + "\n"]
    assert client.closed is True
    assert client.connect_kwargs["look_for_keys"] is False


@pytest.mark.parametrize(
    "reply",
    [
        # FMC host sits between "Manager" and the marker.
        b"Manager fmc.example.com successfully configured.\r\n> ",
        # Interactive shell echoes the typed command before the device reply.
        _CLI_KEY.encode() + b"\r\nManager fmc.example.com successfully configured.\r\n> ",
        # FMC host contains "not" — must not be read as a negation.
        b"Manager not-prod.example.com successfully configured.\r\n> ",
    ],
)
def test_success_variants(monkeypatch: MonkeyPatch, reply: bytes) -> None:
    channel = _FakeChannel([b"\r\n> ", reply])
    client = _FakeClient(channel)
    _patch_client(monkeypatch, client)

    result = _service().configure_manager(
        host="10.0.0.5",
        port=22,
        username="admin",
        password="pw",
        cli_key=_CLI_KEY,
        timeout=5,
    )

    assert result.success is True


def test_success_output_removes_echoed_cli_key(monkeypatch: MonkeyPatch) -> None:
    channel = _FakeChannel(
        [
            b"\r\n> ",
            _CLI_KEY.encode() + b"\r\nManager fmc.example.com successfully configured.\r\n> ",
        ]
    )
    client = _FakeClient(channel)
    _patch_client(monkeypatch, client)

    result = _service().configure_manager(
        host="10.0.0.5",
        port=22,
        username="admin",
        password="pw",
        cli_key=_CLI_KEY,
        timeout=5,
    )

    assert result.success is True
    assert "successfully configured" in result.output.casefold()
    assert _CLI_KEY not in result.output
    assert "regkey123" not in result.output
    assert "natid456" not in result.output


def test_license_confirmation_prompt_is_answered_yes(monkeypatch: MonkeyPatch) -> None:
    channel = _FakeChannel(
        [
            b"\r\n> ",  # initial prompt
            (
                b"If you enabled any feature licenses, you must disable them in Secure "
                b"Firewall Device Manager before deleting the local manager.\r\n"
                b"Do you want to continue[yes/no]: "
            ),
            b"Manager successfully configured.\r\n> ",  # after yes
        ]
    )
    client = _FakeClient(channel)
    _patch_client(monkeypatch, client)

    result = _service().configure_manager(
        host="10.0.0.5",
        port=22,
        username="admin",
        password="pw",
        cli_key=_CLI_KEY,
        timeout=5,
    )

    assert result.success is True
    assert channel.sent == [_CLI_KEY + "\n", "yes\n"]


def test_banner_line_ending_in_arrow_does_not_end_read_early(monkeypatch: MonkeyPatch) -> None:
    # A login banner line ending in "-->" must not be mistaken for the CLI
    # prompt; the read must continue until "> " on its own line.
    channel = _FakeChannel(
        [
            b"WARNING: you must read the EULA -->\r\n",
            b"\r\n> ",
            b"Manager fmc.example.com successfully configured.\r\n> ",
        ]
    )
    client = _FakeClient(channel)
    _patch_client(monkeypatch, client)

    result = _service().configure_manager(
        host="10.0.0.5",
        port=22,
        username="admin",
        password="pw",
        cli_key=_CLI_KEY,
        timeout=5,
    )

    assert result.success is True
    # The command was sent only after the real prompt, not into the banner.
    assert channel.sent == [_CLI_KEY + "\n"]


@pytest.mark.parametrize(
    "reply",
    [
        b"Manager fmc.example.com was not successfully configured.\r\n> ",
        b"DNS successfully configured.\r\n> ",
        b"Error: registration failed.\r\n> ",
        # Registration failed, but an unrelated sub-status line says
        # "successfully configured": the echoed "manager" must not latch onto it.
        _CLI_KEY.encode()
        + b"\r\nManager registration failed.\r\nDNS successfully configured.\r\n> ",
    ],
)
def test_non_manager_or_negated_output_is_not_success(
    monkeypatch: MonkeyPatch, reply: bytes
) -> None:
    channel = _FakeChannel([b"\r\n> ", reply])
    client = _FakeClient(channel)
    _patch_client(monkeypatch, client)

    with pytest.raises(FtdConfigureManagerError, match="did not confirm"):
        _service().configure_manager(
            host="10.0.0.5",
            port=22,
            username="admin",
            password="pw",
            cli_key=_CLI_KEY,
            timeout=5,
        )


def test_error_reply_raises_with_output(monkeypatch: MonkeyPatch) -> None:
    channel = _FakeChannel(
        [
            b"\r\n> ",
            b"Manager already configured.\r\n> ",
        ]
    )
    client = _FakeClient(channel)
    _patch_client(monkeypatch, client)

    with pytest.raises(FtdConfigureManagerError) as excinfo:
        _service().configure_manager(
            host="10.0.0.5",
            port=22,
            username="admin",
            password="pw",
            cli_key=_CLI_KEY,
            timeout=5,
        )

    assert "Manager already configured." in excinfo.value.output
    assert client.closed is True


def test_error_output_removes_echoed_cli_key(monkeypatch: MonkeyPatch) -> None:
    channel = _FakeChannel(
        [
            b"\r\n> ",
            _CLI_KEY.encode() + b"\r\nManager already configured.\r\n> ",
        ]
    )
    client = _FakeClient(channel)
    _patch_client(monkeypatch, client)

    with pytest.raises(FtdConfigureManagerError) as excinfo:
        _service().configure_manager(
            host="10.0.0.5",
            port=22,
            username="admin",
            password="pw",
            cli_key=_CLI_KEY,
            timeout=5,
        )

    assert "Manager already configured." in excinfo.value.output
    assert _CLI_KEY not in excinfo.value.output
    assert "regkey123" not in excinfo.value.output
    assert "natid456" not in excinfo.value.output


def test_authentication_failure_maps_to_error(monkeypatch: MonkeyPatch) -> None:
    client = _FakeClient(_FakeChannel([]))

    def _raise_auth(**kwargs: Any) -> None:
        raise paramiko.AuthenticationException("bad creds")

    monkeypatch.setattr(client, "connect", _raise_auth)
    _patch_client(monkeypatch, client)

    with pytest.raises(FtdConfigureManagerError, match="authentication failed"):
        _service().configure_manager(
            host="10.0.0.5",
            port=22,
            username="admin",
            password="pw",
            cli_key=_CLI_KEY,
            timeout=5,
        )


def test_connection_failure_maps_to_error(monkeypatch: MonkeyPatch) -> None:
    client = _FakeClient(_FakeChannel([]))

    def _raise_conn(**kwargs: Any) -> None:
        raise OSError("no route to host")

    monkeypatch.setattr(client, "connect", _raise_conn)
    _patch_client(monkeypatch, client)

    with pytest.raises(FtdConfigureManagerError, match="Could not establish SSH connection"):
        _service().configure_manager(
            host="10.0.0.5",
            port=22,
            username="admin",
            password="pw",
            cli_key=_CLI_KEY,
            timeout=5,
        )


@pytest.mark.parametrize(
    "bad_key",
    [
        "",
        "   ",
        "configure manager add x\nshow version",
        "show version",
    ],
)
def test_invalid_cli_key_rejected(monkeypatch: MonkeyPatch, bad_key: str) -> None:
    client = _FakeClient(_FakeChannel([]))
    _patch_client(monkeypatch, client)

    with pytest.raises(ValueError):
        _service().configure_manager(
            host="10.0.0.5",
            port=22,
            username="admin",
            password="pw",
            cli_key=bad_key,
            timeout=5,
        )

    # Validation happens before any SSH connection is attempted.
    assert client.connect_kwargs == {}


# --- Jump host ----------------------------------------------------------------


class _FakeTransport:
    def __init__(self) -> None:
        self.opened: list[tuple[Any, ...]] = []

    def open_channel(self, kind: str, dest: Any, src: Any) -> str:
        self.opened.append((kind, dest, src))
        return "jump-sock"


class _FakeJumpClient:
    def __init__(self) -> None:
        self.closed = False
        self.connect_kwargs: dict[str, Any] = {}
        self.transport = _FakeTransport()

    def set_missing_host_key_policy(self, _policy: Any) -> None:
        return None

    def connect(self, **kwargs: Any) -> None:
        self.connect_kwargs = kwargs

    def get_transport(self) -> _FakeTransport:
        return self.transport

    def close(self) -> None:
        self.closed = True


def _patch_clients(monkeypatch: MonkeyPatch, *clients: Any) -> None:
    """Patch paramiko.SSHClient to hand out the given clients in order."""
    queue = list(clients)
    monkeypatch.setattr(svc_mod.paramiko, "SSHClient", lambda: queue.pop(0))


_JUMP = JumpHostSpec(host="jump.example", port=2222, username="bastion", password=None)


def test_configure_via_jump_host(monkeypatch: MonkeyPatch) -> None:
    jump = _FakeJumpClient()
    ftd = _FakeClient(_FakeChannel(list(_SUCCESS_CHUNKS)))
    # _open_jump_channel builds the jump client first, then configure_manager the FTD client.
    _patch_clients(monkeypatch, jump, ftd)

    result = _service().configure_manager(
        host="10.0.0.5",
        port=22,
        username="admin",
        password="pw",
        cli_key=_CLI_KEY,
        timeout=5,
        jump=_JUMP,
    )

    assert result.success is True
    # Jump hop authenticated with keys/agent allowed.
    assert jump.connect_kwargs["hostname"] == "jump.example"
    assert jump.connect_kwargs["port"] == 2222
    assert jump.connect_kwargs["look_for_keys"] is True
    assert jump.connect_kwargs["allow_agent"] is True
    # A direct-tcpip channel was opened to the FTD target...
    assert jump.transport.opened == [("direct-tcpip", ("10.0.0.5", 22), ("", 0))]
    # ...and passed as sock= to the FTD connect.
    assert ftd.connect_kwargs["sock"] == "jump-sock"
    # Both clients are closed.
    assert ftd.closed is True
    assert jump.closed is True


def test_jump_host_auth_failure(monkeypatch: MonkeyPatch) -> None:
    jump = _FakeJumpClient()

    def _raise_auth(**kwargs: Any) -> None:
        raise paramiko.AuthenticationException("bad jump creds")

    monkeypatch.setattr(jump, "connect", _raise_auth)
    _patch_clients(monkeypatch, jump)

    with pytest.raises(FtdConfigureManagerError, match="jump host bastion@jump.example:2222"):
        _service().configure_manager(
            host="10.0.0.5",
            port=22,
            username="admin",
            password="pw",
            cli_key=_CLI_KEY,
            timeout=5,
            jump=_JUMP,
        )

    assert jump.closed is True


def test_check_reachable_direct(monkeypatch: MonkeyPatch) -> None:
    class _Conn:
        def __enter__(self) -> _Conn:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

    monkeypatch.setattr(svc_mod.socket, "create_connection", lambda *a, **k: _Conn())

    result = _service().check_reachable(host="10.0.0.5", port=22, timeout=5)
    assert result.reachable is True


def test_check_reachable_via_jump(monkeypatch: MonkeyPatch) -> None:
    jump = _FakeJumpClient()
    _patch_clients(monkeypatch, jump)

    result = _service().check_reachable(host="10.0.0.5", port=22, timeout=5, jump=_JUMP)
    assert result.reachable is True
    assert "jump host" in result.detail
    assert jump.transport.opened == [("direct-tcpip", ("10.0.0.5", 22), ("", 0))]
    assert jump.closed is True


@pytest.mark.parametrize(
    "value, expected_user, expected_host, expected_port",
    [
        ("bastion@203.0.113.5:2222", "bastion", "203.0.113.5", 2222),
        ("203.0.113.5:2222", None, "203.0.113.5", 2222),
        ("host.example", None, "host.example", 22),
        ("user@host.example", "user", "host.example", 22),
    ],
)
def test_parse_jump_host_valid(
    value: str, expected_user: str | None, expected_host: str, expected_port: int
) -> None:
    spec = parse_jump_host(value, password="secret")
    if expected_user is not None:
        assert spec.username == expected_user
    assert spec.host == expected_host
    assert spec.port == expected_port
    assert spec.password == "secret"


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "user@", "@host", "host:0", "host:99999", "host:abc"],
)
def test_parse_jump_host_invalid(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_jump_host(bad, password=None)

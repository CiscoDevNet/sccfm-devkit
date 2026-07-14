# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for :meth:`FtdConfigureManagerService.delete_manager`."""

from __future__ import annotations

from typing import Any

from _pytest.monkeypatch import MonkeyPatch

from cisco_sccfm_core.services.inventory import FtdConfigureManagerError, FtdConfigureManagerService
from cisco_sccfm_core.services.inventory import ftd_configure_manager_service as svc_mod


class _FakeChannel:
    """Replays one command's scripted output chunks, then the prompt."""

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


class _SequencedClient:
    """Hands out a fresh channel per ``invoke_shell`` (one per CLI command)."""

    def __init__(self, channels: list[_FakeChannel]) -> None:
        self._channels = list(channels)
        self.sent_commands: list[str] = []
        self.closed = 0

    def set_missing_host_key_policy(self, _policy: Any) -> None:
        return None

    def connect(self, **_kwargs: Any) -> None:
        return None

    def invoke_shell(self) -> _FakeChannel:
        channel = self._channels.pop(0)
        return channel

    def close(self) -> None:
        self.closed += 1


def _patch_client(monkeypatch: MonkeyPatch, client: _SequencedClient) -> None:
    monkeypatch.setattr(svc_mod.paramiko, "SSHClient", lambda: client)


def _service() -> FtdConfigureManagerService:
    return FtdConfigureManagerService(config=object())


def _call(host: str = "10.10.3.101") -> Any:
    return dict(host=host, port=22, username="admin", password="pw", timeout=5)


def test_delete_manager_noop_when_already_unmanaged(monkeypatch: MonkeyPatch) -> None:
    # "show managers" reports no manager -> no delete command is issued.
    channels = [_FakeChannel([b"\r\n> ", b"No managers configured.\r\n> "])]
    client = _SequencedClient(channels)
    _patch_client(monkeypatch, client)

    result = _service().delete_manager(**_call())

    assert result.success is True
    assert "No managers configured." in result.output
    # Only the single show-managers connection happened.
    assert client.closed == 1


def test_delete_manager_deletes_then_verifies(monkeypatch: MonkeyPatch) -> None:
    channels = [
        _FakeChannel([b"\r\n> ", b"Type : Manager\r\nHost : fmc.example\r\n> "]),
        _FakeChannel([b"\r\n> ", b"Manager deleted.\r\n> "]),
        _FakeChannel([b"\r\n> ", b"No managers configured.\r\n> "]),
    ]
    client = _SequencedClient(channels)
    _patch_client(monkeypatch, client)

    result = _service().delete_manager(**_call())

    assert result.success is True
    assert result.message == "All managers were removed."
    # show managers -> configure manager delete -> show managers: three
    # connections, each opened and closed.
    assert client.closed == 3


def test_delete_manager_sends_delete_command(monkeypatch: MonkeyPatch) -> None:
    delete_channel = _FakeChannel([b"\r\n> ", b"Manager deleted.\r\n> "])
    channels = [
        _FakeChannel([b"\r\n> ", b"Type : Manager\r\n> "]),
        delete_channel,
        _FakeChannel([b"\r\n> ", b"not currently configured to be managed\r\n> "]),
    ]
    _patch_client(monkeypatch, _SequencedClient(channels))

    _service().delete_manager(**_call())

    assert any("configure manager delete" in sent for sent in delete_channel.sent)


def test_delete_manager_raises_when_still_managed(monkeypatch: MonkeyPatch) -> None:
    channels = [
        _FakeChannel([b"\r\n> ", b"Type : Manager\r\n> "]),
        _FakeChannel([b"\r\n> ", b"Manager deleted.\r\n> "]),
        # Final show still reports a manager -> cleanup failed.
        _FakeChannel([b"\r\n> ", b"Type : Manager\r\nHost : fmc.example\r\n> "]),
    ]
    _patch_client(monkeypatch, _SequencedClient(channels))

    try:
        _service().delete_manager(**_call())
    except FtdConfigureManagerError as exc:
        assert "still has a configured manager" in str(exc)
    else:
        raise AssertionError("Expected FtdConfigureManagerError")

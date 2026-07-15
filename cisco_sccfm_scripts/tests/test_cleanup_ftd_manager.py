# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the guarded FTD manager cleanup script."""

from __future__ import annotations

from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

from cisco_sccfm_core.services.inventory import FtdConfigureManagerError
from cisco_sccfm_scripts import cleanup_ftd_manager as mod


def _clear_env(monkeypatch: MonkeyPatch) -> None:
    for name in (
        "FTD_HOST",
        "SCCFM_E2E_FTD_MANAGER_DELETE_HOST",
        "SCCFM_FTD_PASSWORD",
        "FTD_JUMP_HOST",
        "SCCFM_JUMP_PASSWORD",
        "FTD_PORT",
        "FTD_USER",
        "FTD_SSH_TIMEOUT",
        "FTD_MANAGER_CLEANUP_RETRIES",
        "FTD_MANAGER_CLEANUP_DELAY",
    ):
        monkeypatch.delenv(name, raising=False)


class _RecordingService:
    def __init__(self, fail_times: int = 0) -> None:
        self.calls: list[dict[str, Any]] = []
        self._fail_times = fail_times

    def delete_manager(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if len(self.calls) <= self._fail_times:
            raise FtdConfigureManagerError("boom", output="device said no")
        return object()


def test_returns_false_when_ftd_host_unset(monkeypatch: MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    assert mod.cleanup_manager_from_environment() is False


def test_skips_when_guard_missing(monkeypatch: MonkeyPatch) -> None:
    # FTD_HOST carries its Jenkins-param default on ASA-only runs, but without
    # the delete-host guard the caller did not opt in -> skip, don't raise.
    _clear_env(monkeypatch)
    monkeypatch.setenv("FTD_HOST", "10.10.3.101")
    # SCCFM_E2E_FTD_MANAGER_DELETE_HOST intentionally unset.
    assert mod.cleanup_manager_from_environment() is False


def test_skips_when_password_missing(monkeypatch: MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("FTD_HOST", "10.10.3.101")
    monkeypatch.setenv("SCCFM_E2E_FTD_MANAGER_DELETE_HOST", "10.10.3.101")
    # No SCCFM_FTD_PASSWORD -> registration not requested -> skip.
    assert mod.cleanup_manager_from_environment() is False


def test_refuses_when_guard_mismatches(monkeypatch: MonkeyPatch) -> None:
    # Guard IS set (opt-in) but points at a different host -> hard refusal.
    _clear_env(monkeypatch)
    monkeypatch.setenv("FTD_HOST", "10.10.3.101")
    monkeypatch.setenv("SCCFM_E2E_FTD_MANAGER_DELETE_HOST", "10.10.3.102")
    monkeypatch.setenv("SCCFM_FTD_PASSWORD", "pw")
    with pytest.raises(mod.FtdManagerCleanupError, match="must match exactly"):
        mod.cleanup_manager_from_environment()


def test_happy_path_calls_delete_manager(monkeypatch: MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("FTD_HOST", "10.10.3.101")
    monkeypatch.setenv("SCCFM_E2E_FTD_MANAGER_DELETE_HOST", "10.10.3.101")
    monkeypatch.setenv("SCCFM_FTD_PASSWORD", "pw")
    service = _RecordingService()
    monkeypatch.setattr(mod, "FtdConfigureManagerService", lambda: service)

    assert mod.cleanup_manager_from_environment() is True
    assert len(service.calls) == 1
    assert service.calls[0]["host"] == "10.10.3.101"
    assert service.calls[0]["username"] == "admin"


def test_retries_then_succeeds(monkeypatch: MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("FTD_HOST", "10.10.3.101")
    monkeypatch.setenv("SCCFM_E2E_FTD_MANAGER_DELETE_HOST", "10.10.3.101")
    monkeypatch.setenv("SCCFM_FTD_PASSWORD", "pw")
    monkeypatch.setenv("FTD_MANAGER_CLEANUP_RETRIES", "3")
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    service = _RecordingService(fail_times=2)
    monkeypatch.setattr(mod, "FtdConfigureManagerService", lambda: service)

    assert mod.cleanup_manager_from_environment() is True
    assert len(service.calls) == 3


def test_raises_after_exhausting_retries(monkeypatch: MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("FTD_HOST", "10.10.3.101")
    monkeypatch.setenv("SCCFM_E2E_FTD_MANAGER_DELETE_HOST", "10.10.3.101")
    monkeypatch.setenv("SCCFM_FTD_PASSWORD", "pw")
    monkeypatch.setenv("FTD_MANAGER_CLEANUP_RETRIES", "2")
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    service = _RecordingService(fail_times=99)
    monkeypatch.setattr(mod, "FtdConfigureManagerService", lambda: service)

    with pytest.raises(mod.FtdManagerCleanupError, match="after 2 attempts"):
        mod.cleanup_manager_from_environment()
    assert len(service.calls) == 2

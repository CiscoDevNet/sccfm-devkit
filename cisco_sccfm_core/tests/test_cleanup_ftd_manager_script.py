# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

from cisco_sccfm_core.services.inventory import FtdConfigureManagerError
from cisco_sccfm_scripts import cleanup_ftd_manager as cleanup


class _FakeService:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls: list[dict[str, Any]] = []

    def delete_manager(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)
        if len(self.calls) <= self.failures:
            raise FtdConfigureManagerError("temporary SSH failure")


def _configure_environment(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("FTD_HOST", "10.10.3.105")
    monkeypatch.setenv("SCCFM_E2E_FTD_MANAGER_DELETE_HOST", "10.10.3.105")
    monkeypatch.setenv("SCCFM_FTD_PASSWORD", "secret")
    monkeypatch.setenv("FTD_MANAGER_CLEANUP_DELAY", "1")


def test_cleanup_skips_when_host_is_unset(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("FTD_HOST", raising=False)

    assert cleanup.cleanup_manager_from_environment() is False


def test_cleanup_refuses_host_outside_guard(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("FTD_HOST", "10.10.3.105")
    monkeypatch.setenv("SCCFM_E2E_FTD_MANAGER_DELETE_HOST", "10.10.3.106")

    with pytest.raises(cleanup.FtdManagerCleanupError, match="must match exactly"):
        cleanup.cleanup_manager_from_environment()


def test_cleanup_calls_service_with_environment_values(monkeypatch: MonkeyPatch) -> None:
    _configure_environment(monkeypatch)
    service = _FakeService()
    monkeypatch.setattr(cleanup, "FtdConfigureManagerService", lambda: service)

    assert cleanup.cleanup_manager_from_environment() is True
    assert service.calls == [
        {
            "host": "10.10.3.105",
            "port": 22,
            "username": "admin",
            "password": "secret",
            "timeout": 60,
            "jump": None,
        }
    ]


def test_cleanup_retries_transient_ssh_failure(monkeypatch: MonkeyPatch) -> None:
    _configure_environment(monkeypatch)
    service = _FakeService(failures=1)
    monkeypatch.setattr(cleanup, "FtdConfigureManagerService", lambda: service)
    monkeypatch.setattr(cleanup.time, "sleep", lambda _seconds: None)

    assert cleanup.cleanup_manager_from_environment() is True
    assert len(service.calls) == 2


def test_cleanup_requires_password(monkeypatch: MonkeyPatch) -> None:
    _configure_environment(monkeypatch)
    monkeypatch.delenv("SCCFM_FTD_PASSWORD")

    with pytest.raises(cleanup.FtdManagerCleanupError, match="SCCFM_FTD_PASSWORD"):
        cleanup.cleanup_manager_from_environment()

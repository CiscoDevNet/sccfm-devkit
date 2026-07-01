# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from _pytest.monkeypatch import MonkeyPatch
from scc_firewall_manager_sdk import InventoryApi

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._state import PhaseStateStore
from sccfm_cli.e2e.ftd.phases import cleanup, configure_manager
from sccfm_cli.e2e.ftd.phases.onboard_ftd import _CLI_KEY_STATE


def _context(tmp_path: Path) -> ProfileContext:
    return ProfileContext(
        profile="e2e",
        config_path=tmp_path / "config.json",
        region="ci",
        state=PhaseStateStore(),
    )


def test_cleanup_should_return_before_validation_without_registration_host(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cleanup, "FTD_REGISTRATION_HOST", "")
    monkeypatch.setattr(
        cleanup,
        "validate_registration_name",
        lambda: pytest.fail("cleanup validated an inactive registration fixture"),
    )

    cleanup.run(_context(tmp_path))


def test_cleanup_should_ignore_nonexact_query_matches(monkeypatch: MonkeyPatch) -> None:
    registration_name = "ci-e2e-cli-ftd-lh-109804"
    monkeypatch.setattr(cleanup, "FTD_REGISTRATION_NAME", registration_name)
    exact_match = SimpleNamespace(name=registration_name, uid="exact")
    near_match = SimpleNamespace(name=f"{registration_name}-other", uid="other")
    api = SimpleNamespace(
        get_devices=lambda **_kwargs: SimpleNamespace(items=[exact_match, near_match])
    )

    devices = cleanup._matching_devices(cast(InventoryApi, api))

    assert devices == [exact_match]


def test_configure_manager_should_discard_cli_key_after_failure(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    ctx = _context(tmp_path)
    cli_key = "configure manager add manager.example secret-key nat-id"
    ctx.state.set(_CLI_KEY_STATE, cli_key)

    def fail_cli(*args: str, **kwargs: object) -> None:
        raise AssertionError("SSH failed")

    monkeypatch.setattr(configure_manager, "run_cli", fail_cli)

    with pytest.raises(AssertionError, match="SSH failed"):
        configure_manager.run(ctx)

    with pytest.raises(KeyError, match="phase state missing key"):
        ctx.state.get(_CLI_KEY_STATE)

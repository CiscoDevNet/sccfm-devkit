# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""CI integration tests for ASA shun entry lifecycle.

Tests run sequentially: add shun entries, verify them, remove/clear, verify clean.
All operations are reversible — cleanup clears any residual entries.

Run via:  bash sccfm-ansible/e2e/run_e2e.sh
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import pytest
from conftest import run_playbook

pytestmark = pytest.mark.ci


@dataclass(frozen=True)
class PhaseCase:
    """Single lifecycle phase executed through a focused Ansible playbook."""

    name: str
    playbook: str
    depends_on: tuple[str, ...] = ()


SHUN_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("add_shun", "add_shun.yml"),
    PhaseCase("show_shun", "show_shun.yml", ("add_shun",)),
    PhaseCase("show_shun_statistics", "show_shun_statistics.yml", ("add_shun",)),
    PhaseCase("remove_shun", "remove_shun.yml", ("add_shun",)),
    PhaseCase("clear_shun", "clear_shun.yml", ("add_shun",)),
    PhaseCase("verify_shun_cleared", "verify_shun_cleared.yml", ("clear_shun",)),
)

_phase_failed: set[str] = set()
_phase_succeeded: set[str] = set()


def _skip_if_dependencies_incomplete(*phases: str) -> None:
    """Skip the current test if a required phase failed or never completed."""
    for phase in phases:
        if phase in _phase_failed:
            pytest.skip(f"Skipped because prior phase '{phase}' failed")
        if phase not in _phase_succeeded:
            pytest.skip(f"Skipped because required phase '{phase}' did not complete successfully")


def _run_phase(phase: str, playbook: str) -> None:
    """Run a playbook and record phase success/failure."""
    try:
        run_playbook(playbook)
    except Exception:
        _phase_failed.add(phase)
        raise
    _phase_succeeded.add(phase)


def _run_case(case: PhaseCase) -> None:
    """Evaluate dependencies, then execute a lifecycle phase."""
    _skip_if_dependencies_incomplete(*case.depends_on)
    _run_phase(case.name, case.playbook)


# ── ASA Shun Lifecycle ─────────────────────────────────────────────


class TestAsaShunLifecycle:
    """Shun entry add → show → remove → clear → verify lifecycle."""

    @pytest.mark.parametrize("case", SHUN_PHASES, ids=lambda case: case.name)
    def test_shun_phase(self, case: PhaseCase) -> None:
        _run_case(case)

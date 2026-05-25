# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""CI integration tests for ASA HA health checks.

Each test exercises the asa_ha_check module against an HA-enabled ASA device.
Tests are independent — no dependencies between phases.

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
    """Single test phase executed through a focused Ansible playbook."""

    name: str
    playbook: str
    depends_on: tuple[str, ...] = ()


HA_CHECK_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("ha_check_query", "ha_check_query.yml"),
    PhaseCase("ha_check_query_with_limit", "ha_check_query_with_limit.yml"),
    PhaseCase("ha_check_by_uid", "ha_check_by_uid.yml"),
    PhaseCase("ha_check_assert_structure", "ha_check_assert_structure.yml"),
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
    """Evaluate dependencies, then execute a test phase."""
    _skip_if_dependencies_incomplete(*case.depends_on)
    _run_phase(case.name, case.playbook)


# ── ASA HA Health Checks ──────────────────────────────────────────


class TestAsaHaCheck:
    """HA health checks: query, limit, UID, and structure validation."""

    @pytest.mark.parametrize("case", HA_CHECK_PHASES, ids=lambda case: case.name)
    def test_ha_check_phase(self, case: PhaseCase) -> None:
        _run_case(case)

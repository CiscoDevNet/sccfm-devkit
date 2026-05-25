# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""CI integration tests for ASA upgrade workflow (staging only).

Tests stage an upgrade without rebooting devices. The workflow lists
compatible versions, stages an upgrade, and verifies boot registry.

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


UPGRADE_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("list_versions", "list_compatible_versions_for_upgrade.yml"),
    PhaseCase("stage_upgrade", "trigger_upgrade_stage.yml", ("list_versions",)),
    PhaseCase(
        "verify_boot_after_stage",
        "verify_boot_registry_after_stage.yml",
        ("stage_upgrade",),
    ),
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


# ── ASA Upgrade Workflow ───────────────────────────────────────────


class TestAsaUpgradeWorkflow:
    """Upgrade staging workflow: list versions → stage → verify boot registry."""

    @pytest.mark.parametrize("case", UPGRADE_PHASES, ids=lambda case: case.name)
    def test_upgrade_phase(self, case: PhaseCase) -> None:
        _run_case(case)

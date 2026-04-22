"""CI integration tests for FTD read-only operations.

Each test exercises a read-only FTD module against CI-dedicated devices.
Tests are independent -- no dependencies between phases.

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


READ_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("list_compatible_versions", "list_compatible_versions.yml"),
    PhaseCase("list_not_on_version", "list_not_on_version.yml"),
    PhaseCase("list_not_on_recommended", "list_not_on_recommended.yml"),
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


# -- FTD Read Operations -----------------------------------------------


class TestFtdReadOperations:
    """Read-only FTD operations: compatible versions, not-on-version checks."""

    @pytest.mark.parametrize("case", READ_PHASES, ids=lambda case: case.name)
    def test_read_phase(self, case: PhaseCase) -> None:
        _run_case(case)

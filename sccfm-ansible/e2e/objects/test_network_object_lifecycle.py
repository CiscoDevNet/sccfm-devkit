"""CI integration tests for the network object & group lifecycle.

Tests run sequentially against a real SCCFM tenant. Each test maps to a
focused playbook under playbooks/. Dependent tests are skipped when a
preceding phase fails.

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


OBJECT_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("create", "create_network_objects.yml"),
    PhaseCase("create_idempotency", "create_idempotency.yml", ("create",)),
    PhaseCase("verify_create", "verify_create.yml", ("create",)),
    PhaseCase("update", "update_network_objects.yml", ("create",)),
    PhaseCase("update_idempotency", "update_idempotency.yml", ("update",)),
    PhaseCase("verify_update", "verify_update.yml", ("update",)),
)

GROUP_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("create_group", "create_network_group.yml", ("create",)),
    PhaseCase("update_group", "update_network_group.yml", ("create_group",)),
    PhaseCase("verify_group", "verify_group.yml", ("update_group",)),
    PhaseCase("delete_group", "delete_network_group.yml", ("create_group",)),
)

DELETE_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("delete", "delete_network_objects.yml", ("create",)),
    PhaseCase("delete_idempotency", "delete_idempotency.yml", ("delete",)),
    PhaseCase("verify_delete", "verify_delete.yml", ("delete",)),
)

# Track phase failures so dependent tests can skip.
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


# ── Network Object CRUD ──────────────────────────────────────────


class TestNetworkObjectLifecycle:
    """Network object create → verify → update → delete lifecycle."""

    @pytest.mark.parametrize("case", OBJECT_PHASES, ids=lambda case: case.name)
    def test_object_phase(self, case: PhaseCase) -> None:
        _run_case(case)


# ── Network Group CRUD ───────────────────────────────────────────


class TestNetworkGroupLifecycle:
    """Network group create → update → verify → delete lifecycle."""

    @pytest.mark.parametrize("case", GROUP_PHASES, ids=lambda case: case.name)
    def test_group_phase(self, case: PhaseCase) -> None:
        _run_case(case)


# ── Deletion & Cleanup ──────────────────────────────────────────


class TestDeletion:
    """Delete objects and verify everything is cleaned up."""

    @pytest.mark.parametrize("case", DELETE_PHASES, ids=lambda case: case.name)
    def test_delete_phase(self, case: PhaseCase) -> None:
        _run_case(case)

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""CI integration tests for the access rule lifecycle.

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


SETUP_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("provision_access_group", "provision_access_group.yml"),
)

READ_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase(
        "list_access_groups",
        "list_access_groups.yml",
        ("provision_access_group",),
    ),
    PhaseCase("get_access_group", "get_access_group.yml", ("list_access_groups",)),
    PhaseCase("list_access_rules", "list_access_rules.yml", ("list_access_groups",)),
)

CRUD_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("create", "create_access_rule.yml", ("list_access_groups",)),
    PhaseCase("verify_create", "verify_create.yml", ("create",)),
    PhaseCase("update", "update_access_rule.yml", ("create",)),
    PhaseCase("update_non_idempotency", "update_idempotency.yml", ("update",)),
    PhaseCase("verify_update", "verify_update.yml", ("update",)),
)

DELETE_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("delete", "delete_access_rule.yml", ("create",)),
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


# ── Device Setup ─────────────────────────────────────────────────


class TestSetup:
    """Provision a test access group on the CI ASA (fresh device has none)."""

    @pytest.mark.parametrize("case", SETUP_PHASES, ids=lambda case: case.name)
    def test_setup_phase(self, case: PhaseCase) -> None:
        _run_case(case)


# ── Access Group Read ────────────────────────────────────────────


class TestAccessGroupRead:
    """List access groups and fetch one by UID."""

    @pytest.mark.parametrize("case", READ_PHASES, ids=lambda case: case.name)
    def test_read_phase(self, case: PhaseCase) -> None:
        _run_case(case)


# ── Access Rule CRUD ─────────────────────────────────────────────


class TestAccessRuleLifecycle:
    """Access rule create → verify → update → delete lifecycle."""

    @pytest.mark.parametrize("case", CRUD_PHASES, ids=lambda case: case.name)
    def test_crud_phase(self, case: PhaseCase) -> None:
        _run_case(case)


# ── Deletion & Cleanup ──────────────────────────────────────────


class TestDeletion:
    """Delete access rule and verify it is gone."""

    @pytest.mark.parametrize("case", DELETE_PHASES, ids=lambda case: case.name)
    def test_delete_phase(self, case: PhaseCase) -> None:
        _run_case(case)

"""CI integration tests for the access rule lifecycle.

Tests run sequentially against a real SCCFM tenant.  Each phase invokes
``sccfm-cli`` through a focused phase module under ``phases/``.
Dependent tests are skipped when a preceding phase fails.

Run via:  bash sccfm_cli/e2e/run_e2e.sh
"""

from __future__ import annotations

from typing import Final

import pytest

from sccfm_cli.e2e._phases import PhaseCase, PhaseTracker
from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e.access_rules.phases import (
    create_access_rule,
    delete_access_rule,
    delete_idempotency,
    get_access_group,
    list_access_groups,
    list_access_rules,
    provision_access_group,
    update_access_rule,
    update_idempotency,
    verify_create,
    verify_delete,
    verify_update,
)

pytestmark = pytest.mark.ci

SETUP_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("provision_access_group", provision_access_group.run),
)

READ_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("list_access_groups", list_access_groups.run, ("provision_access_group",)),
    PhaseCase("get_access_group", get_access_group.run, ("list_access_groups",)),
    PhaseCase("list_access_rules", list_access_rules.run, ("list_access_groups",)),
)

CRUD_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("create", create_access_rule.run, ("get_access_group",)),
    PhaseCase("verify_create", verify_create.run, ("create",)),
    PhaseCase("update", update_access_rule.run, ("create",)),
    PhaseCase("update_non_idempotency", update_idempotency.run, ("update",)),
    PhaseCase("verify_update", verify_update.run, ("update",)),
)

DELETE_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("delete", delete_access_rule.run, ("create",)),
    PhaseCase("delete_idempotency", delete_idempotency.run, ("delete",)),
    PhaseCase("verify_delete", verify_delete.run, ("delete",)),
)

_TRACKER = PhaseTracker()


class TestSetup:
    """Provision a test access group on the CI ASA (fresh device has none)."""

    @pytest.mark.parametrize("case", SETUP_PHASES, ids=lambda case: case.name)
    def test_setup_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)


class TestAccessGroupRead:
    """List access groups and fetch one by UID."""

    @pytest.mark.parametrize("case", READ_PHASES, ids=lambda case: case.name)
    def test_read_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)


class TestAccessRuleLifecycle:
    """Access rule create → verify → update lifecycle."""

    @pytest.mark.parametrize("case", CRUD_PHASES, ids=lambda case: case.name)
    def test_crud_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)


class TestDeletion:
    """Delete access rule and verify it is gone."""

    @pytest.mark.parametrize("case", DELETE_PHASES, ids=lambda case: case.name)
    def test_delete_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)

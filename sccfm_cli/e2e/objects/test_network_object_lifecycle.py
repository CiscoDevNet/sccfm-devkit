"""CI integration tests for the network object + group lifecycles.

Tests run sequentially against a real SCCFM tenant.  Each phase invokes
``sccfm-cli`` through a focused phase module under ``phases/``.  Dependent
tests are skipped when a preceding phase fails.

The object, group, and deletion classes share one file (and one tracker)
because the group and deletion phases depend on the object-create phase —
splitting across files would let pytest collect them out of order.

Run via:  bash sccfm_cli/e2e/run_e2e.sh
"""

from __future__ import annotations

from typing import Final

import pytest

from sccfm_cli.e2e._phases import PhaseCase, PhaseTracker
from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e.objects.phases import (
    create_idempotency,
    create_network_group,
    create_network_objects,
    delete_idempotency,
    delete_network_group,
    delete_network_objects,
    update_idempotency,
    update_network_group,
    update_network_objects,
    verify_create,
    verify_delete,
    verify_group,
    verify_update,
)

pytestmark = pytest.mark.ci

_TRACKER = PhaseTracker()

OBJECT_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("create", create_network_objects.run),
    PhaseCase("create_idempotency", create_idempotency.run, ("create",)),
    PhaseCase("verify_create", verify_create.run, ("create",)),
    PhaseCase("update", update_network_objects.run, ("create",)),
    PhaseCase("update_idempotency", update_idempotency.run, ("update",)),
    PhaseCase("verify_update", verify_update.run, ("update",)),
)

GROUP_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("create_group", create_network_group.run, ("create",)),
    PhaseCase("update_group", update_network_group.run, ("create_group",)),
    PhaseCase("verify_group", verify_group.run, ("update_group",)),
    PhaseCase("delete_group", delete_network_group.run, ("create_group",)),
)

DELETE_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("delete", delete_network_objects.run, ("create",)),
    PhaseCase("delete_idempotency", delete_idempotency.run, ("delete",)),
    PhaseCase("verify_delete", verify_delete.run, ("delete",)),
)


class TestNetworkObjectLifecycle:
    """Network object create → verify → update lifecycle."""

    @pytest.mark.parametrize("case", OBJECT_PHASES, ids=lambda case: case.name)
    def test_object_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)


class TestNetworkGroupLifecycle:
    """Network group create → update → verify → delete lifecycle."""

    @pytest.mark.parametrize("case", GROUP_PHASES, ids=lambda case: case.name)
    def test_group_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)


class TestDeletion:
    """Delete objects and verify everything is cleaned up."""

    @pytest.mark.parametrize("case", DELETE_PHASES, ids=lambda case: case.name)
    def test_delete_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)

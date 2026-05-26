"""CI integration tests for the network object lifecycle.

Tests run sequentially against a real SCCFM tenant.  Each phase invokes
``sccfm-cli`` through a focused phase module under ``phases/``.  Dependent
tests are skipped when a preceding phase fails.

Run via:  bash sccfm_cli/e2e/run_e2e.sh
"""

from __future__ import annotations

from typing import Final

import pytest

from sccfm_cli.e2e._phases import PhaseCase
from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e.objects import TRACKER
from sccfm_cli.e2e.objects.phases import (
    create_idempotency,
    create_network_objects,
    update_idempotency,
    update_network_objects,
    verify_create,
    verify_update,
)

pytestmark = pytest.mark.ci

OBJECT_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("create", create_network_objects.run),
    PhaseCase("create_idempotency", create_idempotency.run, ("create",)),
    PhaseCase("verify_create", verify_create.run, ("create",)),
    PhaseCase("update", update_network_objects.run, ("create",)),
    PhaseCase("update_idempotency", update_idempotency.run, ("update",)),
    PhaseCase("verify_update", verify_update.run, ("update",)),
)


class TestNetworkObjectLifecycle:
    """Network object create → verify → update lifecycle."""

    @pytest.mark.parametrize("case", OBJECT_PHASES, ids=lambda case: case.name)
    def test_object_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        TRACKER.run(case, e2e_profile)

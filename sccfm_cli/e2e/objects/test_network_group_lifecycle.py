"""CI integration tests for the network group lifecycle and final cleanup."""

from __future__ import annotations

from typing import Final

import pytest

from sccfm_cli.e2e._phases import PhaseCase
from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e.objects import TRACKER
from sccfm_cli.e2e.objects.phases import (
    create_network_group,
    delete_idempotency,
    delete_network_group,
    delete_network_objects,
    update_network_group,
    verify_delete,
    verify_group,
)

pytestmark = pytest.mark.ci

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


class TestNetworkGroupLifecycle:
    """Network group create → update → verify → delete lifecycle."""

    @pytest.mark.parametrize("case", GROUP_PHASES, ids=lambda case: case.name)
    def test_group_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        TRACKER.run(case, e2e_profile)


class TestDeletion:
    """Delete objects and verify everything is cleaned up."""

    @pytest.mark.parametrize("case", DELETE_PHASES, ids=lambda case: case.name)
    def test_delete_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        TRACKER.run(case, e2e_profile)

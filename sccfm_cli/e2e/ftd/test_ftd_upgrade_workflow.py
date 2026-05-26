"""CI integration tests for FTD upgrade staging."""

from __future__ import annotations

from typing import Final

import pytest

from sccfm_cli.e2e._phases import PhaseCase, PhaseTracker
from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e.ftd.phases import (
    list_compatible_versions_for_upgrade,
    trigger_upgrade_stage,
)

pytestmark = pytest.mark.ci

UPGRADE_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("list_versions", list_compatible_versions_for_upgrade.run),
    PhaseCase("stage_upgrade", trigger_upgrade_stage.run, ("list_versions",)),
)

_TRACKER = PhaseTracker()


class TestFtdUpgradeWorkflow:
    """Upgrade staging workflow: list versions -> stage upgrade."""

    @pytest.mark.parametrize("case", UPGRADE_PHASES, ids=lambda case: case.name)
    def test_upgrade_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)

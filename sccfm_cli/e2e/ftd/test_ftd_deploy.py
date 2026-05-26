"""CI integration test for cdFMC-managed FTD configuration deployment."""

from __future__ import annotations

from typing import Final

import pytest

from sccfm_cli.e2e._phases import PhaseCase, PhaseTracker
from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e.ftd.phases import deploy_ftd

pytestmark = pytest.mark.ci

DEPLOY_PHASES: Final[tuple[PhaseCase, ...]] = (PhaseCase("deploy_ftd", deploy_ftd.run),)

_TRACKER = PhaseTracker()


class TestFtdDeploy:
    """Deploy pending configuration changes to FTD devices."""

    @pytest.mark.parametrize("case", DEPLOY_PHASES, ids=lambda case: case.name)
    def test_deploy_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)

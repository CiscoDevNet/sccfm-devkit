# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""CI integration tests for complete cdFMC-managed FTD registration."""

from __future__ import annotations

from typing import Final

import pytest

from cisco_sccfm_cli.e2e._phases import PhaseCase, PhaseTracker
from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e.ftd.phases import configure_manager, onboard_ftd, verify_registration
from cisco_sccfm_cli.e2e.ftd.phases.test_data import (
    FTD_REGISTRATION_MISSING_ENV,
    FTD_REGISTRATION_REQUIRED,
)

if FTD_REGISTRATION_REQUIRED and FTD_REGISTRATION_MISSING_ENV:
    raise RuntimeError(
        "Required FTD registration E2E inputs are missing: "
        + ", ".join(FTD_REGISTRATION_MISSING_ENV)
    )

pytestmark = [
    pytest.mark.ci,
    pytest.mark.skipif(
        bool(FTD_REGISTRATION_MISSING_ENV),
        reason=(
            "FTD registration E2E inputs are not configured: "
            + ", ".join(FTD_REGISTRATION_MISSING_ENV)
        ),
    ),
]

REGISTRATION_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("onboard", onboard_ftd.run),
    PhaseCase("configure_manager", configure_manager.run, ("onboard",)),
    PhaseCase("verify_registration", verify_registration.run, ("configure_manager",)),
)

_TRACKER = PhaseTracker()


class TestFtdRegistration:
    """Onboard through the API, configure over SSH, then verify ONLINE."""

    @pytest.mark.parametrize("case", REGISTRATION_PHASES, ids=lambda case: case.name)
    def test_registration_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)

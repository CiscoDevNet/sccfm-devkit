# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""CI integration tests for ASA upgrade staging."""

from __future__ import annotations

from typing import Final

import pytest

from cisco_sccfm_cli.e2e._phases import PhaseCase, PhaseTracker
from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e.asa.phases import (
    list_compatible_versions_for_upgrade,
    trigger_upgrade_stage,
    verify_boot_registry_after_stage,
)

pytestmark = pytest.mark.ci

UPGRADE_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("list_versions", list_compatible_versions_for_upgrade.run),
    PhaseCase("stage_upgrade", trigger_upgrade_stage.run, ("list_versions",)),
    PhaseCase(
        "verify_boot_after_stage",
        verify_boot_registry_after_stage.run,
        ("stage_upgrade",),
    ),
)

_TRACKER = PhaseTracker()


class TestAsaUpgradeWorkflow:
    """Upgrade staging workflow: list versions → stage → verify boot registry."""

    @pytest.mark.parametrize("case", UPGRADE_PHASES, ids=lambda case: case.name)
    def test_upgrade_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)

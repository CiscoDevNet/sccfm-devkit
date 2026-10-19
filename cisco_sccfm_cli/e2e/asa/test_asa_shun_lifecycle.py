# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""CI integration tests for the ASA shun entry lifecycle."""

from __future__ import annotations

from typing import Final

import pytest

from cisco_sccfm_cli.e2e._phases import PhaseCase, PhaseTracker
from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e.asa.phases import (
    add_shun,
    clear_shun,
    remove_shun,
    show_shun,
    show_shun_statistics,
    verify_shun_cleared,
)

pytestmark = pytest.mark.ci

SHUN_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("add_shun", add_shun.run),
    PhaseCase("show_shun", show_shun.run, ("add_shun",)),
    PhaseCase("show_shun_statistics", show_shun_statistics.run, ("add_shun",)),
    PhaseCase("remove_shun", remove_shun.run, ("add_shun",)),
    PhaseCase("clear_shun", clear_shun.run, ("add_shun",)),
    PhaseCase("verify_shun_cleared", verify_shun_cleared.run, ("clear_shun",)),
)

_TRACKER = PhaseTracker()


class TestAsaShunLifecycle:
    """Shun entry add → show → remove → clear → verify lifecycle."""

    @pytest.mark.parametrize("case", SHUN_PHASES, ids=lambda case: case.name)
    def test_shun_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)

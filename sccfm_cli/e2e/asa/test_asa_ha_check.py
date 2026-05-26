"""CI integration tests for the ASA ha-check command."""

from __future__ import annotations

from typing import Final

import pytest

from sccfm_cli.e2e._phases import PhaseCase, PhaseTracker
from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e.asa.phases import (
    ha_check_assert_structure,
    ha_check_by_uid,
    ha_check_query,
    ha_check_query_with_limit,
)

pytestmark = pytest.mark.ci

HA_CHECK_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("ha_check_query", ha_check_query.run),
    PhaseCase("ha_check_query_with_limit", ha_check_query_with_limit.run),
    PhaseCase("ha_check_by_uid", ha_check_by_uid.run),
    PhaseCase("ha_check_assert_structure", ha_check_assert_structure.run),
)

_TRACKER = PhaseTracker()


class TestAsaHaCheck:
    """HA health checks: query, limit, UID, and structure validation."""

    @pytest.mark.parametrize("case", HA_CHECK_PHASES, ids=lambda case: case.name)
    def test_ha_check_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)

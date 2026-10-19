# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""CI integration tests for FTD read-only operations."""

from __future__ import annotations

from typing import Final

import pytest

from cisco_sccfm_cli.e2e._phases import PhaseCase, PhaseTracker
from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e.ftd.phases import (
    list_compatible_versions,
    list_not_on_recommended,
    list_not_on_version,
)

pytestmark = pytest.mark.ci

READ_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("list_compatible_versions", list_compatible_versions.run),
    PhaseCase("list_not_on_version", list_not_on_version.run),
    PhaseCase("list_not_on_recommended", list_not_on_recommended.run),
)

_TRACKER = PhaseTracker()


class TestFtdReadOperations:
    """Read-only FTD operations: compatible versions, not-on-version checks."""

    @pytest.mark.parametrize("case", READ_PHASES, ids=lambda case: case.name)
    def test_read_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)

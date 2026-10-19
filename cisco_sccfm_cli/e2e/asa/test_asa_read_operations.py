# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""CI integration tests for ASA read-only operations."""

from __future__ import annotations

from typing import Final

import pytest

from cisco_sccfm_cli.e2e._phases import PhaseCase, PhaseTracker
from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e.asa.phases import (
    execute_cli_read,
    list_boot_registry,
    list_compatible_versions,
    list_disk_files,
    list_local_users,
    list_not_on_version,
)

pytestmark = pytest.mark.ci

READ_PHASES: Final[tuple[PhaseCase, ...]] = (
    PhaseCase("list_boot_registry", list_boot_registry.run),
    PhaseCase("list_compatible_versions", list_compatible_versions.run),
    PhaseCase("list_disk_files", list_disk_files.run),
    PhaseCase("list_local_users", list_local_users.run),
    PhaseCase("list_not_on_version", list_not_on_version.run),
    PhaseCase("execute_cli_read", execute_cli_read.run),
)

_TRACKER = PhaseTracker()


class TestAsaReadOperations:
    """Read-only ASA operations: boot registry, versions, disk, users, CLI."""

    @pytest.mark.parametrize("case", READ_PHASES, ids=lambda case: case.name)
    def test_read_phase(self, case: PhaseCase, e2e_profile: ProfileContext) -> None:
        _TRACKER.run(case, e2e_profile)

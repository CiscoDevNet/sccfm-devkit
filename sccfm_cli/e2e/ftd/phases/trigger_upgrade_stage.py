# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Stage an FTD upgrade (download + readiness check, no reboot).

Skipped unless ``SCCFM_E2E_FTD_UPGRADE_SOFTWARE_VERSION`` is set.
"""

from __future__ import annotations

import pytest

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e.ftd.phases.test_data import (
    FTD_TEST_QUERY,
    FTD_UPGRADE_NAME,
    FTD_UPGRADE_SOFTWARE_VERSION,
)


def run(ctx: ProfileContext) -> None:
    if not FTD_UPGRADE_SOFTWARE_VERSION:
        pytest.skip(
            "FTD upgrade software version not configured "
            "(set SCCFM_E2E_FTD_UPGRADE_SOFTWARE_VERSION)"
        )

    run_cli(
        "inventory",
        "devices",
        "ftd",
        "upgrade",
        "trigger",
        "--query",
        FTD_TEST_QUERY,
        "--software-version",
        FTD_UPGRADE_SOFTWARE_VERSION,
        "--stage-upgrade",
        "--upgrade-name",
        FTD_UPGRADE_NAME,
        "--wait",
        "--timeout",
        "600",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
        timeout=900,
    )

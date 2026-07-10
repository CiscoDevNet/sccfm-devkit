# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Stage an ASA upgrade (download + readiness check, no reboot).

Skipped unless ``SCCFM_E2E_ASA_UPGRADE_SOFTWARE_VERSION`` is set —
matches the Ansible suite's behavior for vASA, which cannot fetch
upgrade images from CDO CloudFront.
"""

from __future__ import annotations

import pytest

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import run_cli
from cisco_sccfm_cli.e2e.asa.phases.test_data import (
    ASA_TEST_QUERY,
    ASA_UPGRADE_ASDM_VERSION,
    ASA_UPGRADE_NAME,
    ASA_UPGRADE_SOFTWARE_VERSION,
)


def run(ctx: ProfileContext) -> None:
    if not ASA_UPGRADE_SOFTWARE_VERSION:
        pytest.skip(
            "ASA upgrade software version not configured "
            "(set SCCFM_E2E_ASA_UPGRADE_SOFTWARE_VERSION)"
        )

    args: list[str] = [
        "inventory",
        "devices",
        "asa",
        "upgrade",
        "trigger",
        "--query",
        ASA_TEST_QUERY,
        "--software-version",
        ASA_UPGRADE_SOFTWARE_VERSION,
    ]
    if ASA_UPGRADE_ASDM_VERSION:
        args += ["--asdm-version", ASA_UPGRADE_ASDM_VERSION]
    args += [
        "--stage-upgrade",
        "--upgrade-name",
        ASA_UPGRADE_NAME,
        "--wait",
        "--timeout",
        "600",
        "--format",
        "json",
    ]

    run_cli(*args, profile=ctx.profile, config_path=ctx.config_path, timeout=900)

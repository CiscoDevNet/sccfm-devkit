# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Remove a single shun entry by source IP."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e.asa.phases.test_data import ASA_TEST_QUERY, SHUN_TEST_SOURCE_IP


def run(ctx: ProfileContext) -> None:
    # --wait so the removal is committed before clear / verify_shun_cleared
    # read device state; otherwise the lifecycle races the backend transaction.
    run_cli(
        "inventory",
        "devices",
        "asa",
        "shun",
        "remove",
        "--query",
        ASA_TEST_QUERY,
        "--source-ip",
        SHUN_TEST_SOURCE_IP,
        "--wait",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
        timeout=600,
    )

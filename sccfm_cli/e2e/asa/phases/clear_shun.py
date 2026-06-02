# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Clear all remaining shun entries on CI ASA devices."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e.asa.phases.test_data import ASA_TEST_QUERY


def run(ctx: ProfileContext) -> None:
    # --wait so all entries are gone before verify_shun_cleared reads state;
    # otherwise the verify phase races the backend transaction.
    run_cli(
        "inventory",
        "devices",
        "asa",
        "shun",
        "clear",
        "--query",
        ASA_TEST_QUERY,
        "--wait",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
        timeout=600,
    )

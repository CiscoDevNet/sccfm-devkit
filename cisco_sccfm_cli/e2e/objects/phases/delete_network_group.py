# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Delete the test network group."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import run_cli
from cisco_sccfm_cli.e2e.objects.phases.test_data import TEST_GROUP_NAME


def run(ctx: ProfileContext) -> None:
    run_cli(
        "objects",
        "network-group",
        "delete",
        "--name",
        TEST_GROUP_NAME,
        profile=ctx.profile,
        config_path=ctx.config_path,
        parse_json=False,
    )

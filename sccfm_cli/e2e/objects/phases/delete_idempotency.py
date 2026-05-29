# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Re-delete: the CLI must reject with non-zero rc (404 / not found)."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e.objects.phases.test_data import TEST_GROUP_NAME, TEST_OBJECT_NAMES


def run(ctx: ProfileContext) -> None:
    run_cli(
        "objects",
        "network-group",
        "delete",
        "--name",
        TEST_GROUP_NAME,
        profile=ctx.profile,
        config_path=ctx.config_path,
        expect_failure=True,
        expected_error=("not found", "not_found", "404"),
        parse_json=False,
    )
    for name in TEST_OBJECT_NAMES:
        run_cli(
            "objects",
            "network",
            "delete",
            "--name",
            name,
            profile=ctx.profile,
            config_path=ctx.config_path,
            expect_failure=True,
            expected_error=("not found", "not_found", "404"),
            parse_json=False,
        )

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Re-delete the rule: the API returns 404 so the CLI exits non-zero."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli


def run(ctx: ProfileContext) -> None:
    rule_uid = ctx.state.get("rule_uid")
    run_cli(
        "policies",
        "access-rule",
        "delete",
        "--uid",
        rule_uid,
        profile=ctx.profile,
        config_path=ctx.config_path,
        expect_failure=True,
        expected_error=("not found", "not_found", "404"),
        parse_json=False,
    )

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Attempt to fetch the deleted rule and confirm the not-found response."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli


def run(ctx: ProfileContext) -> None:
    rule_uid = ctx.state.get("rule_uid")
    result = run_cli(
        "policies",
        "access-rule",
        "get",
        "--uid",
        rule_uid,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
        expect_failure=True,
        parse_json=False,
    )
    combined = (result.stdout + "\n" + result.stderr).lower()
    assert "not found" in combined or "not_found" in combined or "404" in combined, (
        f"Expected a not-found response for rule {rule_uid!r}.\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Update the test rule's remark."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.access_rules.phases.test_data import UPDATED_RULE_REMARK


def run(ctx: ProfileContext) -> None:
    rule_uid = ctx.state.get("rule_uid")
    result = run_cli(
        "policies",
        "access-rule",
        "update",
        "--uid",
        rule_uid,
        "--remark",
        UPDATED_RULE_REMARK,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    assert (
        payload.get("remark") == UPDATED_RULE_REMARK
    ), f"Expected remark={UPDATED_RULE_REMARK!r}, got {payload!r}"

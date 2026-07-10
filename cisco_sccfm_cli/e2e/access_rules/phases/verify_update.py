# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Re-fetch the rule and confirm the updated remark is persisted."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.access_rules.phases.test_data import UPDATED_RULE_REMARK


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
    )
    payload = get_json(result)
    assert (
        payload.get("remark") == UPDATED_RULE_REMARK
    ), f"Expected persisted remark {UPDATED_RULE_REMARK!r}, got {payload!r}"

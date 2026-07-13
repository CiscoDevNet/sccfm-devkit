# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Fetch the created rule by UID and verify its fields."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.access_rules.phases.test_data import TEST_RULE_ACTION, TEST_RULE_REMARK


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
    assert payload.get("uid") == rule_uid, f"Expected uid={rule_uid!r}, got {payload!r}"
    assert (
        payload.get("rule_action") == TEST_RULE_ACTION
    ), f"Expected rule_action={TEST_RULE_ACTION!r}, got {payload!r}"
    assert (
        payload.get("remark") == TEST_RULE_REMARK
    ), f"Expected remark={TEST_RULE_REMARK!r}, got {payload!r}"

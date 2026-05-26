"""Create the test access rule and stash its UID."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.access_rules.phases.test_data import (
    TEST_DESTINATION_NETWORK,
    TEST_RULE_ACTION,
    TEST_RULE_INDEX,
    TEST_RULE_REMARK,
    TEST_SOURCE_NETWORK,
)


def run(ctx: ProfileContext) -> None:
    access_group_uid = ctx.state.get("access_group_uid")
    entity_uid = ctx.state.get("access_group_entity_uid")

    result = run_cli(
        "policies",
        "access-rule",
        "create",
        "--access-group-uid",
        access_group_uid,
        "--entity-uid",
        entity_uid,
        "--index",
        str(TEST_RULE_INDEX),
        "--rule-action",
        TEST_RULE_ACTION,
        "--source-network",
        TEST_SOURCE_NETWORK,
        "--destination-network",
        TEST_DESTINATION_NETWORK,
        "--remark",
        TEST_RULE_REMARK,
        "--active",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    rule_uid = payload.get("uid")
    assert rule_uid, f"Expected access rule UID in response, got {payload!r}"
    assert (
        payload.get("rule_action") == TEST_RULE_ACTION
    ), f"Expected rule_action {TEST_RULE_ACTION!r}, got {payload!r}"
    assert (
        payload.get("remark") == TEST_RULE_REMARK
    ), f"Expected remark {TEST_RULE_REMARK!r}, got {payload!r}"
    ctx.state.set("rule_uid", rule_uid)

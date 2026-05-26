"""Pre/post-test cleanup for the access_rules/ suite.

Order matters: the ACL must come down before the underlying network
objects, since objects can't be deleted while referenced by an ACL.  All
steps tolerate failure so a fresh tenant runs cleanly and a NOT_SYNCED
device after CRUD doesn't block teardown.
"""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e.access_rules.phases.test_data import (
    ASA_TEST_QUERY,
    TEST_ACL_NAME,
    TEST_DESTINATION_NETWORK,
    TEST_SOURCE_NETWORK,
)


def run(ctx: ProfileContext) -> None:
    # ── Access rule cleanup ──────────────────────────────────────
    rule_uid = ctx.state.pop("rule_uid", None)
    if rule_uid:
        run_cli(
            "policies",
            "access-rule",
            "delete",
            "--uid",
            rule_uid,
            profile=ctx.profile,
            config_path=ctx.config_path,
            tolerate_any_rc=True,
            parse_json=False,
        )
    # Drop any cached access-group UID; the next run will rediscover it.
    ctx.state.pop("access_group_uid", None)
    ctx.state.pop("access_group_entity_uid", None)

    # ── Access group teardown via ASA CLI ────────────────────────
    # Tolerate failure: after API CRUD the device is typically
    # NOT_SYNCED and CLI commands are rejected; the next pre-clean
    # will succeed once the device has synced.
    teardown_script = "\n".join(
        [
            "configure terminal",
            f"no access-group {TEST_ACL_NAME} global",
            f"clear configure access-list {TEST_ACL_NAME}",
            "end",
        ]
    )
    run_cli(
        "inventory",
        "devices",
        "asa",
        "cli",
        "execute",
        "--query",
        ASA_TEST_QUERY,
        "--script",
        teardown_script,
        profile=ctx.profile,
        config_path=ctx.config_path,
        tolerate_any_rc=True,
        parse_json=False,
    )

    # ── Network object cleanup ───────────────────────────────────
    for name in (TEST_SOURCE_NETWORK, TEST_DESTINATION_NETWORK):
        run_cli(
            "objects",
            "network",
            "delete",
            "--name",
            name,
            profile=ctx.profile,
            config_path=ctx.config_path,
            tolerate_any_rc=True,
            parse_json=False,
        )

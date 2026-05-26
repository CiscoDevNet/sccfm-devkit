"""List access groups for the test ACL, retrying until CDO indexes it."""

from __future__ import annotations

import time

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.access_rules.phases.test_data import (
    ACCESS_GROUP_QUERY,
    LIST_ACCESS_GROUP_DELAY_SEC,
    LIST_ACCESS_GROUP_RETRIES,
)


def run(ctx: ProfileContext) -> None:
    last_payload: dict[str, object] | None = None
    for _ in range(LIST_ACCESS_GROUP_RETRIES):
        result = run_cli(
            "policies",
            "access-group",
            "list",
            "--query",
            ACCESS_GROUP_QUERY,
            "--limit",
            "10",
            "--format",
            "json",
            profile=ctx.profile,
            config_path=ctx.config_path,
        )
        payload = get_json(result)
        items = payload.get("items") or payload.get("access_groups") or []
        if items:
            ctx.state.set("access_group_uid", items[0]["uid"])
            return
        last_payload = payload
        time.sleep(LIST_ACCESS_GROUP_DELAY_SEC)

    raise AssertionError(
        f"Expected at least one access group for query {ACCESS_GROUP_QUERY!r} "
        f"after {LIST_ACCESS_GROUP_RETRIES} retries.  Last payload: {last_payload!r}"
    )

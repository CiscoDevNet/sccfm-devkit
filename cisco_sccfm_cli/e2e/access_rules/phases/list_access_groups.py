# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""List access groups for the test ACL, retrying until CDO indexes it.

If it never appears, the failure includes read-only diagnostics: the
provisioning response, device sync state, the ACL config on the ASA itself,
and every access group SCCFM knows about.
"""

from __future__ import annotations

import time

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.access_rules.phases.test_data import (
    ACCESS_GROUP_QUERY,
    ASA_TEST_QUERY,
    LIST_ACCESS_GROUP_DELAY_SEC,
    LIST_ACCESS_GROUP_RETRIES,
    TEST_ACL_NAME,
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
        f"after {LIST_ACCESS_GROUP_RETRIES} retries.  Last payload: {last_payload!r}\n"
        f"{_diagnostics(ctx)}"
    )


def _diagnostics(ctx: ProfileContext) -> str:
    """Collect read-only state that explains why no access group appeared."""
    acl_show_script = (
        f"show running-config access-group\nshow running-config access-list {TEST_ACL_NAME}"
    )
    sections = {
        "Provisioning response (error_msg is the ASA's reply)": str(
            ctx.state.pop("provision_cli_output", "(not recorded: provision phase did not finish)")
        ),
        "CI ASA devices and their sync state": _cli_output(
            ctx, "inventory", "devices", "asa", "list", "--query", ASA_TEST_QUERY, "--limit", "10"
        ),
        "ACL config on the ASA itself": _cli_output(
            ctx,
            "inventory",
            "devices",
            "asa",
            "cli",
            "execute",
            "--query",
            ASA_TEST_QUERY,
            "--script",
            acl_show_script,
        ),
        "All access groups, unfiltered": _cli_output(
            ctx, "policies", "access-group", "list", "--limit", "50"
        ),
    }
    return "\n".join(f"--- {title} ---\n{output}" for title, output in sections.items())


def _cli_output(ctx: ProfileContext, *args: str) -> str:
    """Run a diagnostic command as JSON, never raising, so the original failure is kept."""
    try:
        result = run_cli(
            *args,
            "--format",
            "json",
            profile=ctx.profile,
            config_path=ctx.config_path,
            tolerate_any_rc=True,
            parse_json=False,
        )
    except AssertionError as exc:  # run_cli reports timeouts as AssertionError
        return str(exc)
    return (result.stdout + result.stderr).strip() or f"(no output, rc={result.returncode})"

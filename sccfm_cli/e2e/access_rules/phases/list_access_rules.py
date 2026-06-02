# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""List access rules and verify the response shape."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli


def run(ctx: ProfileContext) -> None:
    result = run_cli(
        "policies",
        "access-rule",
        "list",
        "--limit",
        "10",
        "--offset",
        "0",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    items_field = "items" if "items" in payload else "access_rules"
    assert items_field in payload, f"Expected access rules list field in {payload!r}"
    assert "count" in payload, f"Expected 'count' in {payload!r}"
    assert payload.get("limit") == 10, f"Expected limit=10, got {payload!r}"
    assert payload.get("offset") == 0, f"Expected offset=0, got {payload!r}"

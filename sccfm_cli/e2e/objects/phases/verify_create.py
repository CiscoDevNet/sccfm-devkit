# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""List ci-test network objects and verify both fixtures appear."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.objects.phases.test_data import TEST_OBJECT_NAMES, TEST_QUERY


def run(ctx: ProfileContext) -> None:
    result = run_cli(
        "objects",
        "network",
        "list",
        "--query",
        TEST_QUERY,
        "--limit",
        "50",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    items = payload.get("items") or payload.get("network_objects") or []
    names = {item.get("name") for item in items}
    assert payload.get("count", len(items)) >= 2, f"Expected >=2 objects, got {payload!r}"
    for expected in TEST_OBJECT_NAMES:
        assert expected in names, f"Expected {expected!r} in listing, got {sorted(names)!r}"

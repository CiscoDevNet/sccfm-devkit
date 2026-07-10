# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""List host by name and verify the updated literal."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.objects.phases.test_data import TEST_OBJECTS, UPDATED_HOST_VALUE


def run(ctx: ProfileContext) -> None:
    host = TEST_OBJECTS[0]
    result = run_cli(
        "objects",
        "network",
        "list",
        "--query",
        f"name:{host.name}",
        "--limit",
        "1",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    items = payload.get("items") or payload.get("network_objects") or []
    assert items, f"Expected host {host.name!r} in listing, got empty payload {payload!r}"
    assert (
        items[0].get("literal") == UPDATED_HOST_VALUE
    ), f"Expected literal {UPDATED_HOST_VALUE!r}, got {items[0]!r}"

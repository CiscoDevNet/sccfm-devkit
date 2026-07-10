# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""List ci-test objects and groups: nothing should remain."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.objects.phases.test_data import (
    TEST_GROUP_NAME,
    TEST_OBJECT_NAMES,
    TEST_QUERY,
)


def run(ctx: ProfileContext) -> None:
    obj_result = run_cli(
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
    obj_payload = get_json(obj_result)
    obj_items = obj_payload.get("items") or obj_payload.get("network_objects") or []
    obj_names = {item.get("name") for item in obj_items}
    for name in TEST_OBJECT_NAMES:
        assert (
            name not in obj_names
        ), f"Expected {name!r} to be absent after delete, got names {sorted(obj_names)!r}"

    grp_result = run_cli(
        "objects",
        "network-group",
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
    grp_payload = get_json(grp_result)
    grp_items = grp_payload.get("items") or grp_payload.get("network_groups") or []
    grp_names = {item.get("name") for item in grp_items}
    assert (
        TEST_GROUP_NAME not in grp_names
    ), f"Expected {TEST_GROUP_NAME!r} to be absent after delete, got groups {sorted(grp_names)!r}"

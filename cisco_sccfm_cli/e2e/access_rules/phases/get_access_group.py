# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Fetch the cached access group by UID and stash its entity_uid."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli


def run(ctx: ProfileContext) -> None:
    access_group_uid = ctx.state.get("access_group_uid")
    result = run_cli(
        "policies",
        "access-group",
        "get",
        "--uid",
        access_group_uid,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    assert (
        payload.get("uid") == access_group_uid
    ), f"Expected access_group.uid == {access_group_uid!r}, got {payload!r}"
    assert payload.get("name"), f"Expected access_group.name to be set, got {payload!r}"
    entity_uid = payload.get("entity_uid")
    assert entity_uid, f"Expected access_group.entity_uid to be set, got {payload!r}"
    ctx.state.set("access_group_entity_uid", entity_uid)

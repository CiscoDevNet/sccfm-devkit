# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""After clearing, ``shun show`` should report no entries."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._payload import normalize_rows
from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.asa.phases.test_data import ASA_TEST_QUERY


def run(ctx: ProfileContext) -> None:
    result = run_cli(
        "inventory",
        "devices",
        "asa",
        "shun",
        "show",
        "--query",
        ASA_TEST_QUERY,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    rows = normalize_rows(payload)
    # `shun show --format json` returns one row per device shaped like
    # {device_uid, device_name, shun_entries: [...]}; the actual entries are
    # nested under shun_entries, so flatten those rather than inspecting the
    # device-level row keys.
    entries = [
        entry for row in rows for entry in row.get("shun_entries", []) if isinstance(entry, dict)
    ]
    assert not entries, f"Expected no shun entries after clear, got {entries!r}"

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Discover a device UID via query, then re-run HA check using --device-uids."""

from __future__ import annotations

from sccfm_cli.e2e._payload import normalize_rows
from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.asa.phases.test_data import ASA_HA_TEST_QUERY


def run(ctx: ProfileContext) -> None:
    discovery = run_cli(
        "inventory",
        "devices",
        "asa",
        "ha-check",
        "--query",
        ASA_HA_TEST_QUERY,
        "--limit",
        "1",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    discovery_payload = get_json(discovery)
    rows = normalize_rows(discovery_payload)
    assert rows, f"Expected to discover at least one device, got {discovery_payload!r}"
    discovered_uid = rows[0].get("device_uid")
    assert discovered_uid, f"Expected device_uid in discovery result, got {rows[0]!r}"

    by_uid_result = run_cli(
        "inventory",
        "devices",
        "asa",
        "ha-check",
        "--device-uids",
        discovered_uid,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    by_uid_payload = get_json(by_uid_result)
    by_uid_rows = normalize_rows(by_uid_payload)
    assert (
        len(by_uid_rows) == 1
    ), f"Expected one HA result for UID {discovered_uid!r}, got {by_uid_payload!r}"
    assert (
        by_uid_rows[0].get("device_uid") == discovered_uid
    ), f"UID mismatch: expected {discovered_uid!r}, got {by_uid_rows[0]!r}"

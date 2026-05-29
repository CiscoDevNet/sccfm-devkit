# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""List FTD devices not running a fake version."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.ftd.phases.test_data import FTD_NOT_ON_VERSION, FTD_TEST_QUERY


def run(ctx: ProfileContext) -> None:
    result = run_cli(
        "inventory",
        "devices",
        "ftd",
        "list-not-on-version",
        "--query",
        FTD_TEST_QUERY,
        "--version",
        FTD_NOT_ON_VERSION,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    devices = (
        payload.get("devices")
        if isinstance(payload, dict)
        else payload if isinstance(payload, list) else None
    )
    assert devices, f"Expected at least one FTD not on {FTD_NOT_ON_VERSION!r}, got {payload!r}"
    first = devices[0]
    assert first.get("uid"), f"Expected device.uid in first row, got {first!r}"
    assert first.get(
        "software_version"
    ), f"Expected device.software_version in first row, got {first!r}"

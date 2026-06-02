# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""List boot registry data for CI ASA devices."""

from __future__ import annotations

from sccfm_cli.e2e._payload import normalize_rows
from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.asa.phases.test_data import ASA_TEST_QUERY


def run(ctx: ProfileContext) -> None:
    result = run_cli(
        "inventory",
        "devices",
        "asa",
        "list-boot-registry",
        "--query",
        ASA_TEST_QUERY,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    rows = normalize_rows(payload)
    assert rows, f"Expected at least one boot-registry row, got {payload!r}"
    first = rows[0]
    assert first.get("device_uid"), f"Expected device_uid in first row, got {first!r}"

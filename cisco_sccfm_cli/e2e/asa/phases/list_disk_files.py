# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""List disk files on CI ASA devices."""

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
        "disk",
        "list-files",
        "--query",
        ASA_TEST_QUERY,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    rows = normalize_rows(payload)
    assert rows, f"Expected at least one disk-file row, got {payload!r}"
    first = rows[0]
    assert first.get("device_uid") or first.get(
        "device_name"
    ), f"Expected device identifier in first row, got {first!r}"

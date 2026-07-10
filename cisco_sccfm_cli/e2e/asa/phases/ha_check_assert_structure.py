# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Deep structural validation of the HA check output."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._payload import normalize_rows
from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.asa.phases.test_data import (
    ASA_HA_EXPECTED_CHECK_NAMES,
    ASA_HA_TEST_QUERY,
)


def run(ctx: ProfileContext) -> None:
    result = run_cli(
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
    payload = get_json(result)
    rows = normalize_rows(payload)
    assert rows, f"Expected at least one device result, got {payload!r}"
    report = rows[0]

    for field in ("device_uid", "checks"):
        assert report.get(field) is not None, f"Expected per-device field {field!r}, got {report!r}"

    checks = report["checks"]
    assert len(checks) == 7, f"Expected exactly 7 HA checks, got {len(checks)}"

    names = {c.get("name") for c in checks}
    assert names == set(
        ASA_HA_EXPECTED_CHECK_NAMES
    ), f"Check name mismatch.  Expected {sorted(ASA_HA_EXPECTED_CHECK_NAMES)}, got {sorted(names)}"

    for check in checks:
        assert isinstance(check.get("name"), str), f"check.name not a string: {check!r}"
        assert isinstance(check.get("passed"), bool), f"check.passed not a bool: {check!r}"
        assert isinstance(check.get("detail"), str), f"check.detail not a string: {check!r}"

    failover = next(c for c in checks if c["name"] == "failover_enabled")
    assert failover["passed"], f"Expected failover_enabled to pass, got {failover!r}"

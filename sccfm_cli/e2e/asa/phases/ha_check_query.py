"""Run HA health checks on CI HA-enabled ASA devices via query."""

from __future__ import annotations

from sccfm_cli.e2e._payload import normalize_rows
from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.asa.phases.test_data import ASA_HA_TEST_QUERY


def run(ctx: ProfileContext) -> None:
    result = run_cli(
        "inventory",
        "devices",
        "asa",
        "ha-check",
        "--query",
        ASA_HA_TEST_QUERY,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    rows = normalize_rows(payload)
    assert rows, f"Expected at least one HA check result, got {payload!r}"
    first = rows[0]
    assert first.get("device_uid"), f"Expected device_uid in first row, got {first!r}"
    checks = first.get("checks") or []
    assert len(checks) == 7, f"Expected 7 HA checks, got {len(checks)}: {first!r}"

    failover_check = next((c for c in checks if c.get("name") == "failover_enabled"), None)
    assert failover_check and failover_check.get(
        "passed"
    ), f"Expected failover_enabled to pass, got {failover_check!r}"

"""Run HA health checks with the --limit flag set to 1."""

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
        "--limit",
        "1",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    rows = normalize_rows(payload)
    assert len(rows) == 1, f"Expected exactly 1 device result with --limit 1, got {payload!r}"

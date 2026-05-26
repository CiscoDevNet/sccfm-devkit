"""Show active shun entries on CI ASA devices."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.asa.phases.test_data import ASA_TEST_QUERY


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
    assert payload, f"Expected shun data, got {payload!r}"

"""Pre/post cleanup: clear any shun entries left by tests."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e.asa.phases.test_data import ASA_TEST_QUERY_ALL


def run(ctx: ProfileContext) -> None:
    run_cli(
        "inventory",
        "devices",
        "asa",
        "shun",
        "clear",
        "--query",
        ASA_TEST_QUERY_ALL,
        profile=ctx.profile,
        config_path=ctx.config_path,
        tolerate_any_rc=True,
        parse_json=False,
    )

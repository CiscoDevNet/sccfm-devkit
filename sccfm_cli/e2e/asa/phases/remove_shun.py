"""Remove a single shun entry by source IP."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e.asa.phases.test_data import ASA_TEST_QUERY, SHUN_TEST_SOURCE_IP


def run(ctx: ProfileContext) -> None:
    run_cli(
        "inventory",
        "devices",
        "asa",
        "shun",
        "remove",
        "--query",
        ASA_TEST_QUERY,
        "--source-ip",
        SHUN_TEST_SOURCE_IP,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )

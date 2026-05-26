"""Deploy pending configuration to CI cdFMC-managed FTD devices."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e.ftd.phases.test_data import FTD_TEST_QUERY


def run(ctx: ProfileContext) -> None:
    run_cli(
        "inventory",
        "devices",
        "cdfmc-managed-ftd",
        "deploy",
        "--query",
        FTD_TEST_QUERY,
        "--deployment-notes",
        "ci-e2e-ftd-deploy",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )

"""Add shun entries on CI ASA devices using TEST-NET addresses."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e.asa.phases.test_data import ASA_TEST_QUERY, SHUN_TEST_SOURCE_IPS


def run(ctx: ProfileContext) -> None:
    args = ["inventory", "devices", "asa", "shun", "add", "--query", ASA_TEST_QUERY]
    for ip in SHUN_TEST_SOURCE_IPS:
        args += ["--source-ip", ip]
    args += ["--format", "json"]
    run_cli(*args, profile=ctx.profile, config_path=ctx.config_path)

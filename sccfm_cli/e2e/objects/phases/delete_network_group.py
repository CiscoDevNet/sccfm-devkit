"""Delete the test network group."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e.objects.phases.test_data import TEST_GROUP_NAME


def run(ctx: ProfileContext) -> None:
    run_cli(
        "objects",
        "network-group",
        "delete",
        "--name",
        TEST_GROUP_NAME,
        profile=ctx.profile,
        config_path=ctx.config_path,
        parse_json=False,
    )

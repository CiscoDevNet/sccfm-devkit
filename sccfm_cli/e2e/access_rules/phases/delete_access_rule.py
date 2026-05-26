"""Delete the test access rule."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli


def run(ctx: ProfileContext) -> None:
    rule_uid = ctx.state.get("rule_uid")
    run_cli(
        "policies",
        "access-rule",
        "delete",
        "--uid",
        rule_uid,
        profile=ctx.profile,
        config_path=ctx.config_path,
        parse_json=False,
    )

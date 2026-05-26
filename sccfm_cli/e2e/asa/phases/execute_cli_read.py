"""Execute read-only CLI commands on CI ASA devices."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.asa.phases.test_data import ASA_CLI_COMMANDS, ASA_TEST_QUERY


def run(ctx: ProfileContext) -> None:
    script = "\n".join(ASA_CLI_COMMANDS)
    result = run_cli(
        "inventory",
        "devices",
        "asa",
        "cli",
        "execute",
        "--query",
        ASA_TEST_QUERY,
        "--script",
        script,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    assert payload, f"Expected CLI execution payload, got {payload!r}"

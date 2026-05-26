"""After clearing, ``shun show`` should report no entries."""

from __future__ import annotations

from sccfm_cli.e2e._payload import normalize_rows
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
    rows = normalize_rows(payload)
    # An entry row carries a source_ip / src_ip / source field.  Anything else
    # in the payload is metadata (counts, headers) that should not be flagged.
    entries = [row for row in rows if any(k in row for k in ("source_ip", "src_ip", "source"))]
    assert not entries, f"Expected no shun entries after clear, got {entries!r}"

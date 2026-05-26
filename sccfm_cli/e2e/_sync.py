"""Wait for an ASA device to reach SYNCED state.

Phases that push CLI commands to an ASA (`shun add`, `cli execute`,
`provision_access_group`) need the device to be in SYNCED state — the
API rejects script pushes against a NOT_SYNCED device with INVALID_INPUT.

When the e2e suite runs after another suite that mutated the same
device (or after a partial prior run), the device is typically still
re-syncing.  Poll until it reports SYNCED or the timeout fires.
"""

from __future__ import annotations

import time

from sccfm_cli.e2e._payload import normalize_rows
from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli


def wait_for_synced(
    ctx: ProfileContext,
    *,
    query: str,
    retries: int = 30,
    delay_sec: int = 10,
) -> None:
    """Poll ``inventory devices asa list --query <q>`` until SYNCED."""
    last: list[dict[str, object]] | None = None
    for _ in range(retries):
        result = run_cli(
            "inventory",
            "devices",
            "asa",
            "list",
            "--query",
            query,
            "--limit",
            "10",
            "--format",
            "json",
            profile=ctx.profile,
            config_path=ctx.config_path,
        )
        rows = normalize_rows(get_json(result))
        if rows and all(_is_synced(row) for row in rows):
            return
        last = rows
        time.sleep(delay_sec)

    raise AssertionError(
        f"Devices matching {query!r} did not reach SYNCED after {retries * delay_sec}s.\n"
        f"Last poll: {last!r}"
    )


def _is_synced(row: dict[str, object]) -> bool:
    state = row.get("config_state") or row.get("configState")
    return state == "SYNCED"

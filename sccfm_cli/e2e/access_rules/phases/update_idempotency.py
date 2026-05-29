"""Re-apply the same update.

The update path is non-idempotent at the service layer (it always pushes
the payload), but from the CLI's perspective rc=0 and the remark is the
same.  Re-running the update phase asserts the result still reads back
correctly.
"""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e.access_rules.phases.update_access_rule import run as update_run


def run(ctx: ProfileContext) -> None:
    update_run(ctx)

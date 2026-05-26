"""FTD cleanup placeholder.

FTD tests are read-only or use onboard/remove for lifecycle management,
so there is nothing to clear here.  The phase exists so the suite's
``lifecycle_cleanup`` fixture has something to call symmetrically with
the other suites.
"""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext


def run(_ctx: ProfileContext) -> None:
    return None

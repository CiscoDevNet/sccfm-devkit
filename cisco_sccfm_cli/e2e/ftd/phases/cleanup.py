# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""FTD cleanup placeholder.

FTD tests are read-only or use onboard/remove for lifecycle management,
so there is nothing to clear here.  The phase exists so the suite's
``lifecycle_cleanup`` fixture has something to call symmetrically with
the other suites.
"""

from __future__ import annotations

from cisco_sccfm_cli.e2e._profile import ProfileContext


def run(_ctx: ProfileContext) -> None:
    return None

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Phase orchestration shared by every e2e suite.

A :class:`PhaseCase` binds a phase name to a Python callable (the phase
module's ``run`` function) and the phases it depends on.  Each test
module owns its own :class:`PhaseTracker`; when a phase fails, dependent
phases are skipped — same semantics as the Ansible suite, just expressed
in Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pytest

from cisco_sccfm_cli.e2e._profile import ProfileContext


@dataclass(frozen=True)
class PhaseCase:
    name: str
    runner: Callable[[ProfileContext], None]
    depends_on: tuple[str, ...] = ()


class PhaseTracker:
    def __init__(self) -> None:
        self.failed: set[str] = set()
        self.succeeded: set[str] = set()

    def skip_if_dependencies_incomplete(self, *phases: str) -> None:
        for phase in phases:
            if phase in self.failed:
                pytest.skip(f"Skipped because prior phase '{phase}' failed")
            if phase not in self.succeeded:
                pytest.skip(
                    f"Skipped because required phase '{phase}' did not complete successfully"
                )

    def run(self, case: PhaseCase, ctx: ProfileContext) -> None:
        self.skip_if_dependencies_incomplete(*case.depends_on)
        try:
            case.runner(ctx)
        except Exception:
            self.failed.add(case.name)
            raise
        self.succeeded.add(case.name)

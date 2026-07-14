# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""CI integration tests for complete cdFMC-managed FTD registration via Ansible.

Drives the onboard -> configure_manager -> verify path with focused playbooks
against one dedicated persistent FTD (CI: 10.10.3.101). Skipped unless the FTD
inputs are set in the environment; set SCCFM_E2E_REQUIRE_FTD_REGISTRATION=1 to
make missing inputs a hard failure instead of a skip.

Run via:  bash sccfm-ansible/e2e/run_e2e.sh
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

import pytest
from conftest import run_playbook

# FMC_ACCESS_POLICY_UID is intentionally optional: the onboard playbook resolves
# it from the tenant's cdFMC when unset.
_REQUIRED_ENV: Final[tuple[str, ...]] = (
    "FTD_HOST",
    "FTD_PERFORMANCE_TIER",
    "SCCFM_FTD_PASSWORD",
)
_MISSING_ENV: Final[tuple[str, ...]] = tuple(name for name in _REQUIRED_ENV if not os.getenv(name))
_REGISTRATION_REQUIRED = os.getenv("SCCFM_E2E_REQUIRE_FTD_REGISTRATION") == "1"

if _REGISTRATION_REQUIRED and _MISSING_ENV:
    raise RuntimeError(
        "Required FTD registration E2E inputs are missing: " + ", ".join(_MISSING_ENV)
    )

pytestmark = [
    pytest.mark.ci,
    pytest.mark.skipif(
        bool(_MISSING_ENV),
        reason=f"FTD registration E2E inputs are not configured: {', '.join(_MISSING_ENV)}",
    ),
]


@dataclass(frozen=True)
class PhaseCase:
    """Single registration phase executed through a focused Ansible playbook."""

    name: str
    playbook: str
    timeout: int = 600
    depends_on: tuple[str, ...] = ()


REGISTRATION_PHASES: Final[tuple[PhaseCase, ...]] = (
    # The onboarding SCCFM transaction itself can run for up to one hour.
    PhaseCase(
        "onboard_and_configure_manager",
        "onboard_and_configure_ftd.yml",
        timeout=3900,
    ),
    PhaseCase(
        "verify_registration",
        "verify_ftd_registration.yml",
        timeout=1500,
        depends_on=("onboard_and_configure_manager",),
    ),
)

_phase_failed: set[str] = set()
_phase_succeeded: set[str] = set()


def _skip_if_dependencies_incomplete(*phases: str) -> None:
    for phase in phases:
        if phase in _phase_failed:
            pytest.skip(f"Skipped because prior phase '{phase}' failed")
        if phase not in _phase_succeeded:
            pytest.skip(f"Skipped because required phase '{phase}' did not complete successfully")


def _run_case(case: PhaseCase) -> None:
    _skip_if_dependencies_incomplete(*case.depends_on)
    try:
        run_playbook(case.playbook, timeout=case.timeout)
    except Exception:
        _phase_failed.add(case.name)
        raise
    _phase_succeeded.add(case.name)


class TestFtdRegistration:
    """Onboard through the API, configure over SSH, then verify ONLINE."""

    @pytest.mark.parametrize("case", REGISTRATION_PHASES, ids=lambda case: case.name)
    def test_registration_phase(self, case: PhaseCase) -> None:
        _run_case(case)

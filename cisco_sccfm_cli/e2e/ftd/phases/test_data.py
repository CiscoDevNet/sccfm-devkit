# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Test data for the ftd/ e2e suite.

Mirrors ``sccfm-ansible/e2e/ftd/playbooks/vars/test_data.yml``.
"""

from __future__ import annotations

import os
import re


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


# Pre-onboarded FTD device on the CI tenant.
FTD_DEVICE_NAME = "ftd-7.4.2-172-1516"
FTD_TEST_QUERY = f"name:{FTD_DEVICE_NAME} AND connectivityState:ONLINE"
FTD_TEST_QUERY_ALL = f"name:{FTD_DEVICE_NAME}"

# A made-up version no real device is on.
FTD_NOT_ON_VERSION = "99.99.99"

# Registration workflow.  Exercises the full onboard -> configure-manager ->
# verify path against one dedicated persistent FTD (CI: 10.10.3.101).  Every
# input comes from the environment so credentials stay in Jenkins.
FTD_REGISTRATION_HOST = os.environ.get("FTD_HOST", "")
FTD_REGISTRATION_PORT = os.environ.get("FTD_PORT", "22")
FTD_REGISTRATION_USER = os.environ.get("FTD_USER", "admin")
_REGISTRATION_HOST_LABEL = re.sub(r"[^A-Za-z0-9-]", "-", FTD_REGISTRATION_HOST)
# Reserved name prefix; cleanup refuses to delete anything that does not match.
FTD_REGISTRATION_NAME = os.environ.get(
    "SCCFM_E2E_FTD_NAME", f"ci-e2e-cli-ftd-{_REGISTRATION_HOST_LABEL}"
)
_ESCAPED_REGISTRATION_NAME = FTD_REGISTRATION_NAME.replace("\\", "\\\\").replace('"', '\\"')
FTD_REGISTRATION_QUERY = f'name:"{_ESCAPED_REGISTRATION_NAME}"'
# Optional override. When empty, onboard_ftd resolves the access policy at
# runtime from the tenant's cdFMC (manager list -> access-policies list).
FTD_REGISTRATION_ACCESS_POLICY_UID = os.environ.get("FMC_ACCESS_POLICY_UID", "")
# Optional override for which policy to pick when auto-resolving; matched
# case-insensitively against the policy name. Empty means "take the only one".
FTD_REGISTRATION_ACCESS_POLICY_NAME = os.environ.get("FMC_ACCESS_POLICY_NAME", "")
# cdFMC manager lookup used to discover the FMC domain UID when auto-resolving.
FTD_CDFMC_MANAGER_QUERY = os.environ.get("SCCFM_E2E_CDFMC_QUERY", "deviceType:CDFMC")
FTD_REGISTRATION_PERFORMANCE_TIER = os.environ.get("FTD_PERFORMANCE_TIER", "")
FTD_REGISTRATION_JUMP_HOST = os.environ.get("FTD_JUMP_HOST", "")
FTD_REGISTRATION_SSH_TIMEOUT = _env_int("FTD_SSH_TIMEOUT", 60)
FTD_REGISTRATION_RETRIES = _env_int("FTD_REGISTRATION_RETRIES", 120)
FTD_REGISTRATION_DELAY_SEC = _env_int("FTD_REGISTRATION_DELAY", 10)
FTD_CLEANUP_RETRIES = _env_int("FTD_CLEANUP_RETRIES", 60)
# FMC_ACCESS_POLICY_UID is intentionally NOT required: the suite resolves it
# from the tenant's cdFMC when unset.
FTD_REGISTRATION_REQUIRED_ENV = (
    "FTD_HOST",
    "FTD_PERFORMANCE_TIER",
    "SCCFM_FTD_PASSWORD",
)
FTD_REGISTRATION_MISSING_ENV = tuple(
    name for name in FTD_REGISTRATION_REQUIRED_ENV if not os.environ.get(name)
)
# The registration lifecycle (tests AND pre/post cleanup) is active only when
# every required input is present. FTD_HOST alone is not a sufficient signal:
# Jenkins exposes every build parameter as an env var, so FTD_HOST carries its
# default on ASA-only runs too. Gate on the full set instead.
FTD_REGISTRATION_ENABLED = not FTD_REGISTRATION_MISSING_ENV
# When set to "1" the suite must run: missing inputs become a hard error rather
# than a skip, so a misconfigured CI job fails loudly instead of silently.
FTD_REGISTRATION_REQUIRED = os.environ.get("SCCFM_E2E_REQUIRE_FTD_REGISTRATION") == "1"


def validate_registration_name() -> None:
    """Guard: refuse to onboard/clean up any non-reserved device name."""
    if not re.fullmatch(r"ci-e2e-cli-ftd-[A-Za-z0-9-]+", FTD_REGISTRATION_NAME):
        raise AssertionError(
            "Refusing CLI FTD registration or cleanup for non-reserved device name "
            f"{FTD_REGISTRATION_NAME!r}"
        )


# Upgrade workflow.  Disabled by default; opt in via env vars.
FTD_UPGRADE_SOFTWARE_VERSION: str | None = os.environ.get("SCCFM_E2E_FTD_UPGRADE_SOFTWARE_VERSION")
FTD_UPGRADE_NAME = os.environ.get("SCCFM_E2E_FTD_UPGRADE_NAME", "ci-e2e-ftd-upgrade")

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Test data for the ftd/ e2e suite.

Mirrors ``sccfm-ansible/e2e/ftd/playbooks/vars/test_data.yml``.
"""

from __future__ import annotations

import os

# Pre-onboarded FTD device on the CI tenant.
FTD_DEVICE_NAME = "ftd-7.4.2-172-1516"
FTD_TEST_QUERY = f"name:{FTD_DEVICE_NAME} AND connectivityState:ONLINE"
FTD_TEST_QUERY_ALL = f"name:{FTD_DEVICE_NAME}"

# A made-up version no real device is on.
FTD_NOT_ON_VERSION = "99.99.99"

# Upgrade workflow.  Disabled by default; opt in via env vars.
FTD_UPGRADE_SOFTWARE_VERSION: str | None = os.environ.get("SCCFM_E2E_FTD_UPGRADE_SOFTWARE_VERSION")
FTD_UPGRADE_NAME = os.environ.get("SCCFM_E2E_FTD_UPGRADE_NAME", "ci-e2e-ftd-upgrade")

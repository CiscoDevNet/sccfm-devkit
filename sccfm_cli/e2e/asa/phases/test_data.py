"""Test data for the asa/ e2e suite.

Mirrors ``sccfm-ansible/e2e/asa/playbooks/vars/test_data.yml``.
"""

from __future__ import annotations

import os

ASA_TEST_QUERY = "name:ci-e2e-asa-* AND connectivityState:ONLINE"
ASA_TEST_QUERY_ALL = "name:ci-e2e-asa-*"

ASA_CLI_COMMANDS: tuple[str, ...] = (
    "show version",
    "show running-config hostname",
)

# A made-up version no real device is on.
ASA_NOT_ON_VERSION = "9.99(0)"

# RFC 5737 TEST-NET addresses (safe, non-routable).
SHUN_TEST_SOURCE_IP = "198.51.100.1"
SHUN_TEST_SOURCE_IPS: tuple[str, ...] = ("198.51.100.1", "198.51.100.2")

# Upgrade workflow.  Disabled by default — vASA 9.4(1)200 cannot fetch
# upgrade images from CDO CloudFront.  Set these env vars to opt in.
ASA_UPGRADE_SOFTWARE_VERSION: str | None = os.environ.get("SCCFM_E2E_ASA_UPGRADE_SOFTWARE_VERSION")
ASA_UPGRADE_ASDM_VERSION: str | None = os.environ.get("SCCFM_E2E_ASA_UPGRADE_ASDM_VERSION")
ASA_UPGRADE_NAME = os.environ.get("SCCFM_E2E_ASA_UPGRADE_NAME", "ci-e2e-asa-upgrade")

# HA-enabled ASA query.
ASA_HA_TEST_QUERY = "name:asa-ha-951-1516-1110-primary AND connectivityState:ONLINE"

# All 7 HA check names produced by the asa_ha_check service.
ASA_HA_EXPECTED_CHECK_NAMES: frozenset[str] = frozenset(
    {
        "failover_enabled",
        "lan_link",
        "version_match",
        "mate_ready",
        "interfaces_healthy",
        "config_synced",
        "unmonitored_interfaces",
    }
)

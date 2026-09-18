# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Regression tests for compatibility with the generated SDK contract."""

from __future__ import annotations

from scc_firewall_manager_sdk.models.device import Device


def test_inventory_device_accepts_unknown_licensing_statuses() -> None:
    """The API uses UNKNOWN when ASA licensing cannot be determined."""
    device = Device(
        name="asa-1",
        deviceType="ASA",
        complianceStatus="UNKNOWN",
        licenseStatus="UNKNOWN",
    )

    assert device.compliance_status == "UNKNOWN"
    assert device.license_status == "UNKNOWN"

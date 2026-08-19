# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

DOCUMENTATION = r"""
---
module: asa_ha_check
short_description: Run HA health checks on ASA failover devices
description:
  - Performs health checks on ASA High Availability (failover) pairs
    managed by SCC Firewall Manager.
  - Executes C(show failover) and C(show failover state) on the target
    devices, then analyses the output for common HA issues.
  - Queries the ASA Interfaces API to detect enabled interfaces that
    are not monitored for failover — a common misconfiguration that
    can silently break HA.
  - Returns structured check results suitable for assertions in
    playbooks.
  - Devices can be selected by a Lucene query or by specifying UIDs.
options:
  query:
    description:
      - Lucene query to filter ASA devices.
      - Mutually exclusive with C(uids).
      - The query is automatically combined with C(deviceType:ASA).
    required: false
    type: str
  uids:
    description:
      - List of device UIDs to check.
      - Mutually exclusive with C(query).
    required: false
    type: list
    elements: str
  limit:
    description:
      - Maximum number of devices to return when using C(query).
    required: false
    type: int
    default: 50
  offset:
    description:
      - Pagination offset when using C(query).
    required: false
    type: int
    default: 0
  profile:
    description: Named SCCFM profile configured by C(sccfm-cli configure).
    required: false
    type: str
    default: default
  config_path:
    description: Optional path to the canonical SCCFM profile configuration file.
    required: false
    type: path
author:
  - Cisco SCCFM Team (@CiscoDevNet)
"""

EXAMPLES = r"""
# Example 1: Check HA status on devices matching a query
- name: Run HA checks on production ASAs
  cisco.sccfm.asa_ha_check:
    query: "name:prod-ha-* AND connectivityState:ONLINE"
    profile: default
  register: ha_results

# Example 2: Check HA status on a specific device by UID
- name: Run HA checks on a specific ASA
  cisco.sccfm.asa_ha_check:
    uids:
      - "544d3c3b-2440-4b94-8438-74466d95909b"
  register: ha_results

# Example 3: Assert all checks pass
- name: Verify HA health
  cisco.sccfm.asa_ha_check:
    query: "asaFailoverMode:ACTIVE_STANDBY"
  register: ha_results

- name: Fail if any HA check failed
  ansible.builtin.assert:
    that: ha_results.all_passed
    fail_msg: "HA health check failures detected"

# Example 4: Using module_defaults (recommended)
- name: HA health checks
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Run HA checks
      cisco.sccfm.asa_ha_check:
        query: "asaFailoverMode:ACTIVE_STANDBY AND connectivityState:ONLINE"
      register: ha_results
"""

RETURN = r"""
all_passed:
  description: Whether all checks passed across all devices.
  returned: success
  type: bool
results:
  description: >
    List of HA check reports, one per device.
  returned: success
  type: list
  elements: dict
  contains:
    device_uid:
      description: The UID of the device.
      type: str
    all_passed:
      description: Whether all checks passed for this device.
      type: bool
    failover_unit:
      description: The failover unit role (Primary/Secondary).
      type: str
    this_host_state:
      description: Failover state of this host (Active, Standby Ready, etc.).
      type: str
    other_host_state:
      description: Failover state of the mate.
      type: str
    checks:
      description: List of individual check results.
      type: list
      elements: dict
      contains:
        name:
          description: Check name.
          type: str
        passed:
          description: Whether the check passed.
          type: bool
        detail:
          description: Human-readable detail.
          type: str
    unmonitored_interfaces:
      description: Enabled interfaces not monitored for failover.
      type: list
      elements: dict
      contains:
        hardware_name:
          description: Hardware interface name.
          type: str
        name:
          description: Interface nameif.
          type: str
"""


from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException, CdoTransaction, DevicePage

    from cisco_sccfm_core import (
        ASA_DEVICE_TYPE_FILTER,
        AsaHaCheckReport,
        AsaHaCheckService,
        InventoryService,
        SccApiError,
    )
except ImportError as exc:
    record_import_error(exc)
    ApiException = RuntimeError
    NotFoundError = LookupError
    FtdConfigureManagerError = ValueError


from ..module_utils.config import base_argument_spec, create_config


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        **base_argument_spec(),
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
    }


def _serialize_report(
    device_uid: str,
    report: AsaHaCheckReport,
) -> dict[str, Any]:
    """Convert an HA check report into a dict for Ansible output."""
    return {
        "device_uid": device_uid,
        "all_passed": all(c.passed for c in report.checks),
        "failover_unit": report.failover_status.failover_unit,
        "this_host_state": report.failover_status.this_host.state,
        "other_host_state": report.failover_status.other_host.state,
        "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in report.checks],
        "unmonitored_interfaces": [
            {"hardware_name": u.hardware_name, "name": u.name}
            for u in report.unmonitored_interfaces
        ],
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[["query", "uids"]],
        required_one_of=[["query", "uids"]],
        supports_check_mode=True,
    )

    config = create_config(module)

    try:
        device_uids = _resolve_device_uids(module)
        service = AsaHaCheckService(config=config)
        results = service.check_ha(device_uids=device_uids)

        if isinstance(results, CdoTransaction):
            module.fail_json(
                msg=f"HA check failed with status: {results.cdo_transaction_status}",
                transaction_uid=results.transaction_uid,
                error_message=results.error_message,
                transaction_details=results.transaction_details,
            )

        reports = [_serialize_report(uid, report) for uid, report in results.items()]
        all_passed = all(r["all_passed"] for r in reports)

        module.exit_json(
            changed=False,
            msg=f"HA checks completed on {len(device_uids)} device(s)",
            all_passed=all_passed,
            results=reports,
        )

    except ApiException as e:
        error = SccApiError.from_exception(e)
        module.fail_json(**error.to_dict())
    except Exception as e:
        module.fail_json(msg=f"Unexpected error: {str(e)}")


def _resolve_device_uids(module: AnsibleModule) -> list[str]:
    uids: list[str] | None = module.params.get("uids")
    if uids:
        return uids

    config = create_config(module)
    query = cast(str, module.params.get("query"))
    inventory_service = InventoryService(config=config)
    page: DevicePage = inventory_service.get_devices(
        limit=module.params["limit"],
        offset=module.params["offset"],
        query=f"({query}) AND {ASA_DEVICE_TYPE_FILTER}",
    )
    device_uids = [device.uid for device in (page.items or [])]
    if not device_uids:
        module.fail_json(msg="No devices found matching the specified query.")
    return device_uids


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

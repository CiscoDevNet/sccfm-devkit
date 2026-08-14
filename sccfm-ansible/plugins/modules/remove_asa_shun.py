# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException, CdoCliResult, CdoTransaction, DevicePage

from cisco_sccfm_core import ASA_DEVICE_TYPE_FILTER, AsaShunService, InventoryService, SccApiError

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: remove_asa_shun
short_description: Remove one or more shun entries from ASA devices
description:
  - Removes shun entries for specific source IP addresses from one or more
    ASA devices managed by SCC Firewall Manager.
  - Use C(source_ip) for a single removal, or C(source_ips) to remove
    multiple IPs in a single API call (more efficient than looping).
  - Executes C(no shun <source_ip>) on the target devices for each IP.
  - C(source_ip) and C(source_ips) are mutually exclusive.
  - Devices can be selected by a Lucene query or by specifying a list of UIDs.
  - See the SCC Firewall Manager API documentation for
    U(https://developer.cisco.com/docs/cisco-security-cloud-control-firewall-manager/execute-cli-command/).
    for API documentation.
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
      - List of device UIDs to remove the shun from.
      - Mutually exclusive with C(query).
    required: false
    type: list
    elements: str
  source_ip:
    description:
      - The source IP address to remove from the shun list.
      - Mutually exclusive with C(source_ips).
    required: false
    type: str
  source_ips:
    description:
      - A list of source IP addresses to remove from the shun list.
      - All removals are sent in a single transaction.
      - Mutually exclusive with C(source_ip).
    required: false
    type: list
    elements: str
  limit:
    description:
      - Maximum number of devices to return when using C(query).
      - Ignored when using C(uids).
    required: false
    type: int
    default: 50
  offset:
    description:
      - Pagination offset when using C(query).
      - Ignored when using C(uids).
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
  - Cisco SCCFM Team
"""

EXAMPLES = r"""
# Example 1: Remove a single shun on devices matching a query
- name: Remove shun for attacker IP on production ASAs
  cisco.sccfm.remove_asa_shun:
    query: "name:prod-* AND connectivityState:ONLINE"
    source_ip: "10.99.99.99"
    profile: default

# Example 2: Remove multiple shuns in a single transaction
- name: Remove multiple attacker IPs in one call
  cisco.sccfm.remove_asa_shun:
    query: "connectivityState:ONLINE"
    source_ips:
      - "203.0.113.40"
      - "203.0.113.50"
      - "203.0.113.60"
    profile: default

# Example 3: Remove a shun on specific devices by UID
- name: Remove shun on specific ASA
  cisco.sccfm.remove_asa_shun:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
    source_ip: "10.99.99.99"

# Example 4: Using module_defaults (recommended)
- name: Remove shun entries
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Remove shun for attacker
      cisco.sccfm.remove_asa_shun:
        query: "connectivityState:ONLINE"
        source_ip: "10.99.99.99"
"""

RETURN = r"""
results:
  description: List of CLI execution results per device.
  returned: success
  type: list
  elements: dict
  contains:
    device_uid:
      description: The UID of the device.
      type: str
    result:
      description: The CLI command output.
      type: str
    error_msg:
      description: Error message if execution failed on this device (None if successful).
      type: str
    script:
      description: The script that was executed.
      type: str
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        **base_argument_spec(),
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "source_ip": {"type": "str", "required": False},
        "source_ips": {"type": "list", "elements": "str", "required": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[["query", "uids"], ["source_ip", "source_ips"]],
        required_one_of=[["query", "uids"], ["source_ip", "source_ips"]],
        supports_check_mode=True,
    )

    config = create_config(module)
    source_ip: str | None = module.params.get("source_ip")
    source_ips_param: list[str] | None = module.params.get("source_ips")

    if source_ip is not None:
        ips_to_remove = [source_ip]
        display_subject = source_ip
    else:
        ips_to_remove = source_ips_param or []
        if not ips_to_remove:
            module.fail_json(msg="source_ips must contain at least one IP address.")
        display_subject = f"{len(ips_to_remove)} IPs"

    try:
        device_uids = _resolve_device_uids(module)

        if module.check_mode is True:
            module.exit_json(
                changed=True,
                msg=f"Would remove shun for {display_subject} on {len(device_uids)} device(s)",
                results=[],
            )
            return

        service = AsaShunService(config=config)
        results: CdoTransaction | list[CdoCliResult] = service.remove_shun_entries(
            device_uids=device_uids,
            source_ips=ips_to_remove,
        )

        if isinstance(results, CdoTransaction):
            module.fail_json(
                msg=f"Remove shun failed with status: {results.cdo_transaction_status}",
                transaction_uid=results.transaction_uid,
                error_message=results.error_message,
                transaction_details=results.transaction_details,
            )

        results_data = [result.model_dump(mode="json") for result in results]
        module.exit_json(
            changed=True,
            msg=f"Successfully removed shun for {display_subject} on {len(device_uids)} device(s)",
            results=results_data,
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

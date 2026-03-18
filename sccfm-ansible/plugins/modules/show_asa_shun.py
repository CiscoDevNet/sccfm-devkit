from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException, CdoTransaction, DevicePage

from sccfm_core import AsaShunService, InventoryService, SccApiError
from sccfm_core.models.asa_shun_entry import AsaShunEntry, AsaShunInterfaceStats

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: show_asa_shun
short_description: Show shun entries or statistics on ASA devices
description:
  - Lists active shun entries on one or more ASA devices managed by
    SCC Firewall Manager.
  - Executes C(show shun) on the target devices and returns structured data
    with interface, source/destination IP, ports, and protocol.
  - When C(statistics) is set to C(true), executes C(show shun statistics)
    instead and returns per-interface shun/received counters.
  - Devices can be selected by a Lucene query or by specifying a list of UIDs.
  - See U(https://developer.cisco.com/docs/cisco-security-cloud-control-firewall-manager/execute-cli-command/)
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
      - List of device UIDs to query.
      - Mutually exclusive with C(query).
    required: false
    type: list
    elements: str
  statistics:
    description:
      - When C(true), show per-interface shun statistics instead of shun entries.
    required: false
    type: bool
    default: false
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
  region:
    description: SCCFM region (int, us, eu, apj, aus, uae, or in).
    required: false
    type: str
    env:
      - name: SCCFM_REGION
  api_token:
    description: API token for SCCFM.
    required: false
    type: str
    no_log: true
    env:
      - name: SCCFM_API_TOKEN
author:
  - Cisco SCCFM Team
"""

EXAMPLES = r"""
# Example 1: Show shun entries on devices matching a query
- name: Show shun entries on production ASAs
  cisco.sccfm.show_asa_shun:
    query: "name:prod-* AND connectivityState:ONLINE"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: shun_entries

# Example 2: Show shun entries on specific devices by UID
- name: Show shun entries on specific ASAs
  cisco.sccfm.show_asa_shun:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
  register: shun_entries

# Example 3: Show shun statistics
- name: Show shun statistics on ASAs
  cisco.sccfm.show_asa_shun:
    query: "connectivityState:ONLINE"
    statistics: true
  register: shun_stats

# Example 4: Using module_defaults (recommended)
- name: Show shun info
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: Show shun entries
      cisco.sccfm.show_asa_shun:
        query: "connectivityState:ONLINE"
      register: shun_entries

    - name: Show shun statistics
      cisco.sccfm.show_asa_shun:
        query: "connectivityState:ONLINE"
        statistics: true
      register: shun_stats
"""

RETURN = r"""
results:
  description: >
    List of shun entries or statistics found on the target devices.
    The structure depends on the C(statistics) flag.
  returned: success
  type: list
  elements: dict
  contains:
    device_uid:
      description: The UID of the device.
      type: str
    interface:
      description: The interface name (returned for both entries and statistics).
      type: str
    source_ip:
      description: The shunned source IP address (entries only).
      type: str
    destination_ip:
      description: The destination IP address (entries only).
      type: str
    source_port:
      description: The source port (entries only).
      type: int
    destination_port:
      description: The destination port (entries only).
      type: int
    protocol:
      description: The IP protocol number (entries only).
      type: int
    shunned:
      description: Number of shunned connections on this interface (statistics only).
      type: int
    received:
      description: Number of received packets on this interface (statistics only).
      type: int
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        **base_argument_spec(),
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "statistics": {"type": "bool", "required": False, "default": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
    }


def _serialize_entries(
    results: dict[str, list[AsaShunEntry]],
) -> list[dict[str, Any]]:
    """Convert parsed shun entries into a flat list of dicts for Ansible output."""
    output: list[dict[str, Any]] = []
    for device_uid, entries in results.items():
        for e in entries:
            output.append(
                {
                    "device_uid": device_uid,
                    "interface": e.interface,
                    "source_ip": e.source_ip,
                    "destination_ip": e.destination_ip,
                    "source_port": e.source_port,
                    "destination_port": e.destination_port,
                    "protocol": e.protocol,
                }
            )
    return output


def _serialize_statistics(
    results: dict[str, list[AsaShunInterfaceStats]],
) -> list[dict[str, Any]]:
    """Convert parsed shun statistics into a flat list of dicts for Ansible output."""
    output: list[dict[str, Any]] = []
    for device_uid, stats in results.items():
        for s in stats:
            output.append(
                {
                    "device_uid": device_uid,
                    "interface": s.interface,
                    "shunned": s.shunned,
                    "received": s.received,
                }
            )
    return output


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[["query", "uids"]],
        required_one_of=[["query", "uids"]],
    )

    config = create_config(module)
    statistics: bool = module.params["statistics"]

    try:
        device_uids = _resolve_device_uids(module)

        service = AsaShunService(config=config)

        if statistics:
            results = service.view_shun_statistics(device_uids=device_uids)
            if isinstance(results, CdoTransaction):
                module.fail_json(
                    msg=f"Show shun statistics failed with status: {results.cdo_transaction_status}",
                    transaction_uid=results.transaction_uid,
                    error_message=results.error_message,
                    transaction_details=results.transaction_details,
                )
            results_data = _serialize_statistics(results)
            label = "statistics"
        else:
            results = service.view_shun(device_uids=device_uids)
            if isinstance(results, CdoTransaction):
                module.fail_json(
                    msg=f"Show shun failed with status: {results.cdo_transaction_status}",
                    transaction_uid=results.transaction_uid,
                    error_message=results.error_message,
                    transaction_details=results.transaction_details,
                )
            results_data = _serialize_entries(results)
            label = "entries"

        module.exit_json(
            changed=False,
            msg=f"Successfully retrieved shun {label} from {len(device_uids)} device(s)",
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
        query=f"({query}) AND deviceType:ASA",
    )
    device_uids = [device.uid for device in (page.items or [])]
    if not device_uids:
        module.fail_json(msg="No devices found matching the specified query.")
    return device_uids


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

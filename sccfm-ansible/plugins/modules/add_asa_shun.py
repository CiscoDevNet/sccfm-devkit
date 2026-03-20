from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException, CdoCliResult, CdoTransaction, DevicePage

from sccfm_core import AsaShunService, InventoryService, SccApiError
from sccfm_core.services.inventory.asa_shun_service import ShunEntrySpec

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: add_asa_shun
short_description: Add one or more shun entries on ASA devices
description:
  - Adds shun entries on one or more ASA devices managed by
    SCC Firewall Manager.
  - Use C(source_ip) for a single entry, or C(entries) to add multiple
    entries in a single API call (more efficient than looping).
  - Executes C(shun <source_ip>) to block all future connections from that host.
  - Optionally specify a connection tuple (C(dest_ip), C(source_port),
    C(dest_port), C(protocol)) to additionally drop an existing connection
    immediately.
  - C(source_ip) and C(entries) are mutually exclusive.
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
      - List of device UIDs to add the shun on.
      - Mutually exclusive with C(query).
    required: false
    type: list
    elements: str
  source_ip:
    description:
      - The source IP address of the attacking host to block.
      - Mutually exclusive with C(entries).
    required: false
    type: str
  dest_ip:
    description:
      - Destination IP of a specific connection to drop immediately.
      - Required when specifying C(source_port), C(dest_port), or C(protocol).
      - Only valid when using C(source_ip) (not C(entries)).
    required: false
    type: str
  source_port:
    description:
      - Source port of the connection to drop.
      - Requires C(dest_ip).
      - Only valid when using C(source_ip) (not C(entries)).
    required: false
    type: int
  dest_port:
    description:
      - Destination port of the connection to drop.
      - Requires C(dest_ip).
      - Only valid when using C(source_ip) (not C(entries)).
    required: false
    type: int
  protocol:
    description:
      - Protocol of the connection to drop (tcp or udp).
      - Requires C(dest_ip).
      - Only valid when using C(source_ip) (not C(entries)).
    required: false
    type: str
    choices:
      - tcp
      - udp
  entries:
    description:
      - List of shun entries to add in a single transaction.
      - Mutually exclusive with C(source_ip).
      - Each entry must have C(source_ip) and may optionally include
        C(dest_ip), C(source_port), C(dest_port), and C(protocol).
    required: false
    type: list
    elements: dict
    suboptions:
      source_ip:
        description: The source IP address to block.
        required: true
        type: str
      dest_ip:
        description: Destination IP of a specific connection to drop immediately.
        required: false
        type: str
      source_port:
        description: Source port of the connection to drop (requires dest_ip).
        required: false
        type: int
      dest_port:
        description: Destination port of the connection to drop (requires dest_ip).
        required: false
        type: int
      protocol:
        description: Protocol of the connection to drop — tcp or udp (requires dest_ip).
        required: false
        type: str
        choices:
          - tcp
          - udp
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
# Example 1: Shun a single source IP on devices matching a query
- name: Block attacker on production ASAs
  cisco.sccfm.add_asa_shun:
    query: "name:prod-* AND connectivityState:ONLINE"
    source_ip: "10.99.99.99"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 2: Shun with connection tuple to drop an existing connection
- name: Block attacker and drop active connection
  cisco.sccfm.add_asa_shun:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
    source_ip: "10.99.99.99"
    dest_ip: "10.1.1.1"
    source_port: 555
    dest_port: 666
    protocol: tcp

# Example 3: Shun multiple IPs in a single transaction (recommended for bulk)
- name: Block multiple attackers in one API call
  cisco.sccfm.add_asa_shun:
    query: "connectivityState:ONLINE"
    entries:
      - source_ip: "203.0.113.40"
      - source_ip: "203.0.113.50"
        dest_ip: "10.1.1.1"
        source_port: 555
        dest_port: 443
        protocol: tcp
      - source_ip: "203.0.113.60"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 4: Using module_defaults (recommended)
- name: Add shun entries
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: Shun attacker IP
      cisco.sccfm.add_asa_shun:
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
        "dest_ip": {"type": "str", "required": False},
        "source_port": {"type": "int", "required": False},
        "dest_port": {"type": "int", "required": False},
        "protocol": {"type": "str", "required": False, "choices": ["tcp", "udp"]},
        "entries": {"type": "list", "elements": "dict", "required": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[["query", "uids"], ["source_ip", "entries"]],
        required_one_of=[["query", "uids"], ["source_ip", "entries"]],
    )

    config = create_config(module)
    source_ip: str | None = module.params.get("source_ip")
    entries_raw: list[dict[str, Any]] | None = module.params.get("entries")

    if source_ip is not None:
        dest_ip: str | None = module.params.get("dest_ip")
        source_port: int | None = module.params.get("source_port")
        dest_port: int | None = module.params.get("dest_port")
        protocol: str | None = module.params.get("protocol")

        has_conn_params = any(p is not None for p in (source_port, dest_port, protocol))
        if has_conn_params and dest_ip is None:
            module.fail_json(
                msg="dest_ip is required when specifying source_port, dest_port, or protocol."
            )
        entries = [
            ShunEntrySpec(
                source_ip=source_ip,
                dest_ip=dest_ip,
                source_port=source_port,
                dest_port=dest_port,
                protocol=protocol,
            )
        ]
        display_subject = source_ip
    else:
        entries = _parse_entries(module, entries_raw or [])
        display_subject = f"{len(entries)} entries"

    try:
        device_uids = _resolve_device_uids(module)

        service = AsaShunService(config=config)
        results: CdoTransaction | list[CdoCliResult] = service.add_shun_entries(
            device_uids=device_uids,
            entries=entries,
        )

        if isinstance(results, CdoTransaction):
            module.fail_json(
                msg=f"Add shun failed with status: {results.cdo_transaction_status}",
                transaction_uid=results.transaction_uid,
                error_message=results.error_message,
                transaction_details=results.transaction_details,
            )

        results_data = [result.model_dump(mode="json") for result in results]
        module.exit_json(
            changed=True,
            msg=f"Successfully added shun for {display_subject} on {len(device_uids)} device(s)",
            results=results_data,
        )

    except ApiException as e:
        error = SccApiError.from_exception(e)
        module.fail_json(**error.to_dict())
    except Exception as e:
        module.fail_json(msg=f"Unexpected error: {str(e)}")


def _parse_entries(module: AnsibleModule, raw: list[dict[str, Any]]) -> list[ShunEntrySpec]:
    """Validate and convert the raw ``entries`` list into :class:`ShunEntrySpec` objects."""
    if not raw:
        module.fail_json(msg="entries must contain at least one item.")
    specs: list[ShunEntrySpec] = []
    for i, item in enumerate(raw):
        src = item.get("source_ip")
        if not src:
            module.fail_json(msg=f"entries[{i}]: source_ip is required.")
        dest_ip = item.get("dest_ip")
        source_port = item.get("source_port")
        dest_port = item.get("dest_port")
        protocol = item.get("protocol")
        has_conn_params = any(p is not None for p in (source_port, dest_port, protocol))
        if has_conn_params and dest_ip is None:
            module.fail_json(
                msg=(
                    f"entries[{i}]: dest_ip is required when specifying "
                    "source_port, dest_port, or protocol."
                )
            )
        specs.append(
            ShunEntrySpec(
                source_ip=src,
                dest_ip=dest_ip,
                source_port=source_port,
                dest_port=dest_port,
                protocol=protocol,
            )
        )
    return specs


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

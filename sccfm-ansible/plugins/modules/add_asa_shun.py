from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException, CdoCliResult, CdoTransaction, DevicePage

from sccfm_core import AsaShunService, InventoryService, SccApiError
from sccfm_core.types import ConfigLike

from ..module_utils.config import Config

DOCUMENTATION = r"""
---
module: add_asa_shun
short_description: Add a shun entry on ASA devices
description:
  - Adds a shun entry on one or more ASA devices managed by
    SCC Firewall Manager.
  - Executes C(shun <source_ip>) to block all future connections from that host.
  - Optionally specify a connection tuple (C(dest_ip), C(source_port),
    C(dest_port), C(protocol)) to additionally drop an existing connection
    immediately.
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
    required: true
    type: str
  dest_ip:
    description:
      - Destination IP of a specific connection to drop immediately.
      - Required when specifying C(source_port), C(dest_port), or C(protocol).
    required: false
    type: str
  source_port:
    description:
      - Source port of the connection to drop.
      - Requires C(dest_ip).
    required: false
    type: int
  dest_port:
    description:
      - Destination port of the connection to drop.
      - Requires C(dest_ip).
    required: false
    type: int
  protocol:
    description:
      - Protocol of the connection to drop (tcp or udp).
      - Requires C(dest_ip).
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
# Example 1: Shun a source IP on devices matching a query
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

# Example 3: Using module_defaults (recommended)
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
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "source_ip": {"type": "str", "required": True},
        "dest_ip": {"type": "str", "required": False},
        "source_port": {"type": "int", "required": False},
        "dest_port": {"type": "int", "required": False},
        "protocol": {"type": "str", "required": False, "choices": ["tcp", "udp"]},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
        "region": {"type": "str", "required": False},
        "api_token": {"type": "str", "required": False, "no_log": True},
    }


def resolve_device_uids_from_query(
    config: ConfigLike,
    query: str,
    limit: int,
    offset: int,
) -> list[str]:
    """Resolve device UIDs from a query. Returns empty list if no devices match."""
    inventory_service = InventoryService(config=config)
    page: DevicePage = inventory_service.get_devices(
        limit=limit,
        offset=offset,
        query=f"{query} AND deviceType:ASA",
    )
    return [device.uid for device in (page.items or [])]


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[["query", "uids"]],
        required_one_of=[["query", "uids"]],
    )

    try:
        config = Config(
            region=module.params.get("region") or "",
            api_token=module.params.get("api_token") or "",
        )
    except ValueError as e:
        module.fail_json(msg=str(e))

    query: str | None = module.params.get("query")
    uids: list[str] | None = module.params.get("uids")
    source_ip: str = module.params["source_ip"]
    dest_ip: str | None = module.params.get("dest_ip")
    source_port: int | None = module.params.get("source_port")
    dest_port: int | None = module.params.get("dest_port")
    protocol: str | None = module.params.get("protocol")
    limit: int = module.params["limit"]
    offset: int = module.params["offset"]

    # Validate connection tuple parameters
    has_conn_params = any(p is not None for p in (source_port, dest_port, protocol))
    if has_conn_params and dest_ip is None:
        module.fail_json(
            msg="dest_ip is required when specifying source_port, dest_port, or protocol."
        )

    try:
        if uids:
            device_uids = uids
        else:
            device_uids = resolve_device_uids_from_query(
                config=config,
                query=cast(str, query),
                limit=limit,
                offset=offset,
            )
            if not device_uids:
                module.fail_json(msg="No devices found matching the specified query.")

        service = AsaShunService(config=config)
        results: CdoTransaction | list[CdoCliResult] = service.add_shun(
            device_uids=device_uids,
            source_ip=source_ip,
            dest_ip=dest_ip,
            source_port=source_port,
            dest_port=dest_port,
            protocol=protocol,
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
            msg=f"Successfully added shun for {source_ip} on {len(device_uids)} device(s)",
            results=results_data,
        )

    except ApiException as e:
        error = SccApiError.from_exception(e)
        module.fail_json(**error.to_dict())
    except Exception as e:
        module.fail_json(msg=f"Unexpected error: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

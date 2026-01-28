from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction, DevicePage

from sccfm_core import AsaCommandLineService, InventoryService
from sccfm_core.types import ConfigLike

from ..module_utils.config import Config, resolve_connection_params

DOCUMENTATION = r"""
---
module: execute_asa_cli
short_description: Execute CLI commands on ASA devices via SCC Firewall Manager
description:
  - Execute CLI commands on one or more ASA devices managed by SCC Firewall Manager.
  - Devices can be selected by query or by explicit UUIDs.
options:
  query:
    description:
      - Lucene query to filter ASA devices.
      - Mutually exclusive with C(uuids).
      - The query is automatically combined with C(deviceType:ASA).
    required: false
    type: str
  uuids:
    description:
      - List of device UUIDs to execute commands on.
      - Mutually exclusive with C(query).
    required: false
    type: list
    elements: str
  commands:
    description:
      - List of ASA CLI commands to execute.
      - Commands are executed in order.
    required: true
    type: list
    elements: str
  limit:
    description:
      - Maximum number of devices to return when using C(query).
      - Ignored when using C(uuids).
    required: false
    type: int
    default: 50
  offset:
    description:
      - Pagination offset when using C(query).
      - Ignored when using C(uuids).
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
# Example 1: Execute commands on devices matching a query
- name: Show version on all production ASAs
  cisco.sccfm.execute_asa_cli:
    query: "name:prod-*"
    commands:
      - "show version"
      - "show running-config"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: cli_results

# Example 2: Execute commands on specific devices by UUID
- name: Show interface on specific ASAs
  cisco.sccfm.execute_asa_cli:
    uuids:
      - "12345678-1234-1234-1234-123456789abc"
      - "87654321-4321-4321-4321-cba987654321"
    commands:
      - "show interface"
  register: cli_results

# Example 3: Using module_defaults (recommended)
- name: Execute CLI commands on ASAs
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: Show version on branch ASAs
      cisco.sccfm.execute_asa_cli:
        query: "name:branch-*"
        commands:
          - "show version"

# Example 4: Load commands from a file
- name: Execute commands from file
  cisco.sccfm.execute_asa_cli:
    query: "name:prod-*"
    commands: "{{ lookup('file', 'scripts/show_commands.txt').splitlines() }}"
"""

RETURN = r"""
results:
  description: List of CLI execution results per device.
  returned: success
  type: list
  elements: dict
  contains:
    device_uid:
      description: The UUID of the device.
      type: str
    result:
      description: The CLI command output.
      type: str
    error_msg:
      description: Error message if execution failed on this device.
      type: str
    script:
      description: The script that was executed.
      type: str
    execution_uid:
      description: The UUID of the CLI execution.
      type: str
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "query": {"type": "str", "required": False},
        "uuids": {"type": "list", "elements": "str", "required": False},
        "commands": {"type": "list", "elements": "str", "required": True},
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


def execute_cli_commands(
    config: ConfigLike,
    device_uids: list[str],
    commands: list[str],
) -> list[CdoCliResult] | CdoTransaction:
    """Execute CLI commands on devices."""
    cli_service = AsaCommandLineService(config=config)
    return cli_service.execute_cli(device_uids=device_uids, asa_commands=commands)


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[["query", "uuids"]],
        required_one_of=[["query", "uuids"]],
    )

    region, api_token = resolve_connection_params(module)
    try:
        config = Config(region=region, api_token=api_token)
    except ValueError as e:
        module.fail_json(msg=str(e))

    query: str | None = module.params.get("query")
    uuids: list[str] | None = module.params.get("uuids")
    commands: list[str] = module.params["commands"]
    limit: int = module.params["limit"]
    offset: int = module.params["offset"]

    try:
        # Resolve device UIDs: use provided UUIDs directly, or query for them
        if uuids:
            device_uids = uuids
        else:
            device_uids = resolve_device_uids_from_query(
                config=config,
                query=cast(str, query),
                limit=limit,
                offset=offset,
            )
            if not device_uids:
                module.fail_json(msg="No devices found matching the specified query.")

        results = execute_cli_commands(
            config=config,
            device_uids=device_uids,
            commands=commands,
        )

        if isinstance(results, CdoTransaction):
            module.fail_json(
                msg=f"CLI execution failed with status: {results.cdo_transaction_status}",
                transaction_uid=results.transaction_uid,
                error_message=results.error_message,
                transaction_details=results.transaction_details,
            )

        results_data = [result.to_dict() for result in results]
        module.exit_json(
            changed=True,
            msg=f"Successfully executed CLI commands on {len(device_uids)} device(s)",
            results=results_data,
        )

    except Exception as e:
        module.fail_json(msg=f"Failed to execute CLI commands: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException, CdoCliResult, CdoTransaction, DevicePage

from sccfm_core import ASA_DEVICE_TYPE_FILTER, AsaCommandLineService, InventoryService, SccApiError
from sccfm_core.types import ConfigLike

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: execute_asa_cli
short_description: Execute CLI commands on ASA devices via SCC Firewall Manager
description:
  - Execute CLI commands on one or more ASA devices managed by SCC Firewall Manager.
  - Devices can be selected by a Lucene query or by specifying a list of UIDs.
  - The query uses the same syntax as the Get Devices API.
  - See U(https://developer.cisco.com/docs/cisco-security-cloud-control-firewall-manager/get-devices/) for query documentation.
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
      - List of device UIDs to execute commands on.
      - Mutually exclusive with C(query).
    required: false
    type: list
    elements: str
  command:
    description:
      - Single ASA CLI command to execute.
      - Mutually exclusive with C(commands). Use C(commands) to run more than one command.
    required: false
    type: str
  commands:
    description:
      - List of ASA CLI commands to execute.
      - Commands are executed in order.
      - Mutually exclusive with C(command).
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
  region:
    description: SCCFM region (int, us, eu, apj, au, uae, in, or ci).
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
    query: "name:prod-* AND connectivityState:ONLINE"
    commands:
      - "show version"
      - "show running-config"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: cli_results

# Example 2: Execute commands on specific devices by UID
- name: Show interface on specific ASAs
  cisco.sccfm.execute_asa_cli:
    uids:
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
        query: "name:branch-* AND connectivityState:ONLINE"
        command: "show version"

# Example 4: Use Ansible's lookup to read commands from a file (one command per line)
- name: Execute commands from file
  cisco.sccfm.execute_asa_cli:
    query: "name:prod-* AND connectivityState:ONLINE"
    commands: "{{ lookup('file', 'scripts/show_commands.txt').splitlines() }}"
"""

RETURN = r"""
command:
  description: The CLI script that was executed. Multiple commands are joined with newlines.
  returned: success
  type: str
commands:
  description: List of ASA CLI commands that were executed.
  returned: success
  type: list
  elements: str
device_count:
  description: Number of target devices matched by the module.
  returned: success
  type: int
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
    execution_uid:
      description: The UID of the CLI execution.
      type: str
    start_time:
      description: The time the CLI execution started (ISO 8601 format).
      type: str
    uid:
      description: The UID of the CLI result.
      type: str
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "command": {"type": "str", "required": False},
        "commands": {"type": "list", "elements": "str", "required": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
        **base_argument_spec(),
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
        query=f"{query} AND {ASA_DEVICE_TYPE_FILTER}",
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


def _normalize_commands(module: AnsibleModule) -> list[str]:
    command: str | None = module.params.get("command")
    commands: list[str] | None = module.params.get("commands")
    normalized = [command] if command else list(commands or [])
    if not normalized:
        module.fail_json(msg="Provide either 'command' or 'commands'.")
    return normalized


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[["query", "uids"], ["command", "commands"]],
        required_one_of=[["query", "uids"], ["command", "commands"]],
        supports_check_mode=True,
    )

    config: Config = create_config(module)
    query: str | None = module.params.get("query")
    uids: list[str] | None = module.params.get("uids")
    commands = _normalize_commands(module)
    command_script = "\n".join(commands)
    limit: int = module.params["limit"]
    offset: int = module.params["offset"]

    try:
        # Resolve device UIDs: use provided UIDs directly, or query for them
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

        if module.check_mode is True:
            module.exit_json(
                changed=True,
                msg=f"Would execute CLI commands on {len(device_uids)} device(s)",
                command=command_script,
                commands=commands,
                device_count=len(device_uids),
                results=[],
            )
            return

        results: list[CdoCliResult] | CdoTransaction = execute_cli_commands(
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

        results_data = [result.model_dump(mode="json") for result in results]
        module.exit_json(
            changed=True,
            msg=f"Successfully executed CLI commands on {len(device_uids)} device(s)",
            command=command_script,
            commands=commands,
            device_count=len(device_uids),
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

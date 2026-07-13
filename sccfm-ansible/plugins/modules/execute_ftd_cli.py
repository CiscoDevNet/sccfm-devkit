# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException, Device, DevicePage

from cisco_sccfm_core import CDFMC_MANAGED_FTD_DEVICE_TYPE_FILTER, InventoryService, SccApiError
from cisco_sccfm_core.models.ftd_cli_result import FtdBulkCliResult
from cisco_sccfm_core.services.inventory.ftd_cli_service import (
    FtdCommandLineService,
    _validate_show_command,
)
from cisco_sccfm_core.types import ConfigLike

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: execute_ftd_cli
short_description: Execute show commands on cdFMC-managed FTD devices via SCC Firewall Manager
description:
  - Execute a show command on one or more cdFMC-managed FTD devices.
  - Devices can be selected by a Lucene query or by specifying a list of UIDs.
  - Only show commands are supported (e.g. show version, show failover, show route).
  - The command runs via the cdFMC bulk command proxy endpoint.
  - See U(https://developer.cisco.com/docs/cisco-security-cloud-control-firewall-manager/create-bulk-command/) for endpoint documentation.
options:
  query:
    description:
      - Lucene query to filter cdFMC-managed FTD devices.
      - Mutually exclusive with C(uids).
      - The query is automatically combined with C(deviceType:CDFMC_MANAGED_FTD).
    required: false
    type: str
  uids:
    description:
      - List of device UIDs to execute the command on.
      - Mutually exclusive with C(query).
    required: false
    type: list
    elements: str
  command:
    description:
      - The show command to execute on the FTD devices.
      - Only show commands are supported (e.g. show version, show failover).
      - Mutually exclusive with C(commands).
    required: false
    type: str
  commands:
    description:
      - Single-item list containing the show command to execute on the FTD devices.
      - Mutually exclusive with C(command). FTD bulk execution supports one command per request.
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
# Example 1: Execute a show command on devices matching a query
- name: Show failover on all production FTDs
  cisco.sccfm.execute_ftd_cli:
    query: "name:prod-* AND connectivityState:ONLINE"
    command: "show failover"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: cli_results

# Example 2: Execute a command on specific devices by UID
- name: Show version on specific FTDs
  cisco.sccfm.execute_ftd_cli:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
      - "87654321-4321-4321-4321-cba987654321"
    command: "show version"
  register: cli_results

# Example 3: Using module_defaults (recommended)
- name: Execute show commands on FTDs
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: Show route on branch FTDs
      cisco.sccfm.execute_ftd_cli:
        query: "name:branch-* AND connectivityState:ONLINE"
        command: "show route"
"""

RETURN = r"""
command:
  description: The show command that was executed.
  returned: success
  type: str
commands:
  description: Single-item command list that was executed.
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
    device_uuid:
      description: The FMC device record UUID.
      type: str
    device_name:
      description: The device name.
      type: str
    response:
      description: The CLI command output (null if error).
      type: str
    is_error:
      description: Whether execution failed on this device.
      type: bool
    error_msg:
      description: Error message if execution failed (null if successful).
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


def resolve_ftd_devices(
    config: ConfigLike,
    *,
    query: str | None,
    uids: list[str] | None,
    limit: int,
    offset: int,
) -> list[Device]:
    inventory_service = InventoryService(config=config)
    if uids:
        uid_query = " OR ".join(f"uid:{uid}" for uid in uids)
        page: DevicePage = inventory_service.get_devices(
            limit=len(uids),
            offset=0,
            query=f"({uid_query}) AND {CDFMC_MANAGED_FTD_DEVICE_TYPE_FILTER}",
        )
    else:
        page = inventory_service.get_devices(
            limit=limit,
            offset=offset,
            query=f"({query}) AND {CDFMC_MANAGED_FTD_DEVICE_TYPE_FILTER}",
        )
    return list(page.items or [])


def _normalize_command(module: AnsibleModule) -> str:
    command: str | None = module.params.get("command")
    commands: list[str] | None = module.params.get("commands")
    if command:
        return command
    normalized_commands = list(commands or [])
    if len(normalized_commands) != 1:
        module.fail_json(
            msg=(
                "execute_ftd_cli accepts exactly one command. "
                "Use 'command' or provide a single-item 'commands' list."
            )
        )
    return normalized_commands[0]


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
        mutually_exclusive=[["query", "uids"], ["command", "commands"]],
        required_one_of=[["query", "uids"], ["command", "commands"]],
    )

    config: Config = create_config(module)
    query: str | None = module.params.get("query")
    uids: list[str] | None = module.params.get("uids")
    command = _normalize_command(module)
    limit: int = module.params["limit"]
    offset: int = module.params["offset"]

    try:
        devices = resolve_ftd_devices(
            config=config,
            query=query,
            uids=uids,
            limit=limit,
            offset=offset,
        )
        if not devices:
            module.fail_json(msg="No devices found matching the specified filter.")

        if module.check_mode:
            normalized_command = _validate_show_command(command)
            module.exit_json(
                changed=False,
                msg=f"Would execute '{normalized_command}' on {len(devices)} device(s).",
                command=normalized_command,
                commands=[normalized_command],
                results=[],
                device_count=len(devices),
            )

        cli_service = FtdCommandLineService(config=config)
        result: FtdBulkCliResult = cli_service.execute_cli(
            devices=devices,
            command=command,
        )

        results_data = [
            {
                "device_uuid": r.device_uuid,
                "device_name": r.device_name,
                "response": r.response,
                "is_error": r.is_error,
                "error_msg": r.error_msg,
            }
            for r in result.device_responses
        ]

        module.exit_json(
            changed=False,
            msg=f"Successfully executed '{command}' on {len(devices)} device(s)",
            command=result.command,
            commands=[result.command],
            device_count=len(devices),
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

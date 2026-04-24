from __future__ import annotations

import json
from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException, CdoCliResult, CdoTransaction, DevicePage

from sccfm_core import ASA_DEVICE_TYPE_FILTER, AsaCommandLineService, InventoryService, SccApiError
from sccfm_core.parsers import normalize_cli_output, parse_cli_table, rows_to_dicts
from sccfm_core.types import ConfigLike

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: list_asa_local_users
short_description: List local users on ASA devices using SCC Firewall Manager
description:
  - Retrieve the ASA local user table by executing `show aaa local user` on selected devices.
  - Devices can be selected by a Lucene query or by supplying a list of UIDs.
options:
  query:
    description:
      - Lucene query to filter ASA devices.
      - Mutually exclusive with C(uids).
    required: false
    type: str
  uids:
    description:
      - List of device UIDs to execute the command on.
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
  region:
    description: SCCFM region (int, us, eu, apj, au, uae, in, or ci).
    required: false
    type: str
    env:
      - name: SCCFM_REGION
  api_token:
    description: API token for SCCFM
    required: false
    type: str
    no_log: true
    env:
      - name: SCCFM_API_TOKEN
author:
  - Cisco SCCFM Team
"""

EXAMPLES = r"""
- name: List local users on one or more devices by UID
  cisco.sccfm.list_asa_local_users:
    uids:
      - "544d3c3b-2440-4b94-8438-74466d95909b"
      - "abcdef01-2345-6789-abcd-ef0123456789"

- name: List local users using a query
  cisco.sccfm.list_asa_local_users:
    query: "name:branch-* AND connectivityState:ONLINE"
    region: "us"
    api_token: "{{ sccfm_api_token }}"

- name: List local users with shared auth
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: List local users on branch ASAs
      cisco.sccfm.list_asa_local_users:
        query: "name:branch-* AND connectivityState:ONLINE"
"""

RETURN = r"""
results:
  description: Raw CLI execution results per device.
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
      description: Error message if execution failed on this device.
      type: str
asa_local_users:
  description: >-
    Mapping of device name (or UID) to its list of parsed local-user records.
  returned: success
  type: dict
  sample:
    asa-to-upgrade-2:
      - user: abragg
        failed_attempts: "0"
        locked: "N"
asa_local_users_json:
  description: Pretty-printed JSON string of C(asa_local_users) for human-readable output.
  returned: success
  type: str
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
        **base_argument_spec(),
    }


def resolve_devices_from_query(
    config: ConfigLike,
    query: str,
    limit: int,
    offset: int,
) -> tuple[list[str], dict[str, str]]:
    """Return ``(uids, uid_to_name)`` for devices matching *query*."""
    inventory_service = InventoryService(config=config)
    page: DevicePage = inventory_service.get_devices(
        limit=limit, offset=offset, query=f"{query} AND {ASA_DEVICE_TYPE_FILTER}"
    )
    uids: list[str] = []
    names: dict[str, str] = {}
    for device in page.items or []:
        uids.append(device.uid)
        names[device.uid] = getattr(device, "name", "") or ""
    return uids, names


def execute_cli_command(
    config: ConfigLike,
    device_uids: list[str],
) -> list[CdoCliResult] | CdoTransaction:
    """Execute ``show aaa local user`` on the given devices."""
    cli_service = AsaCommandLineService(config=config)
    return cli_service.execute_cli(device_uids=device_uids, asa_commands=["show aaa local user"])


def resolve_devices_from_uids(
    config: ConfigLike,
    device_uids: list[str],
) -> tuple[list[str], dict[str, str]]:
    """Return ``(uids, uid_to_name)`` for devices matching *device_uids* via bulk query."""
    inventory_service = InventoryService(config=config)
    query = " OR ".join([f"uid:{uid}" for uid in device_uids])
    page: DevicePage = inventory_service.get_devices(limit=len(device_uids), offset=0, query=query)
    uids: list[str] = []
    names: dict[str, str] = {}
    for device in page.items or []:
        uids.append(device.uid)
        names[device.uid] = getattr(device, "name", "") or ""
    return uids, names


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[["query", "uids"]],
        required_one_of=[["query", "uids"]],
        supports_check_mode=True,
    )

    if module.check_mode is True:
        module.exit_json(
            changed=False,
            msg="Check mode: local-user lookup would run against the selected ASA devices.",
            results=[],
            asa_local_users={},
            asa_local_users_json="{}",
        )

    config: Config = create_config(module)
    query: str | None = module.params.get("query")
    uids: list[str] | None = module.params.get("uids")
    limit: int = module.params.get("limit")
    offset: int = module.params.get("offset")

    try:
        if uids:
            device_uids, device_names = resolve_devices_from_uids(config=config, device_uids=uids)
        else:
            device_uids, device_names = resolve_devices_from_query(
                config=config, query=cast(str, query), limit=limit, offset=offset
            )

        if not device_uids:
            module.fail_json(msg="No devices found matching the specified filter.")

        results: list[CdoCliResult] | CdoTransaction = execute_cli_command(
            config=config, device_uids=device_uids
        )

        if isinstance(results, CdoTransaction):
            module.fail_json(
                msg=f"CLI execution failed with status: {results.cdo_transaction_status}",
                transaction_uid=results.transaction_uid,
                error_message=results.error_message,
                transaction_details=results.transaction_details,
            )

        results_data = [result.model_dump(mode="json") for result in results]

        # Build a mapping of device_name (fallback to uid) -> parsed users
        asa_local_users: dict[str, list[dict[str, str]]] = {}
        for result in results:
            raw = getattr(result, "result", "") or ""
            uid = getattr(result, "device_uid", "")
            key = device_names.get(uid, "") or uid
            headers, rows = parse_cli_table(normalize_cli_output(raw), max_columns=None)
            asa_local_users[key] = rows_to_dicts(headers, rows)

        module.exit_json(
            changed=False,
            msg=f"Successfully retrieved local users from {len(device_uids)} device(s)",
            results=results_data,
            asa_local_users=asa_local_users,
            asa_local_users_json=json.dumps(asa_local_users, indent=2),
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

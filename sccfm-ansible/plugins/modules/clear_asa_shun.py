from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException, CdoCliResult, CdoTransaction, DevicePage

from sccfm_core import AsaShunService, InventoryService, SccApiError
from sccfm_core.types import ConfigLike

from ..module_utils.config import Config

DOCUMENTATION = r"""
---
module: clear_asa_shun
short_description: Clear all shun entries and statistics on ASA devices
description:
  - Clears all active shun entries and resets shun statistics on one or more
    ASA devices managed by SCC Firewall Manager.
  - Executes C(clear shun) on the target devices.
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
      - List of device UIDs to clear shuns on.
      - Mutually exclusive with C(query).
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
# Example 1: Clear all shuns on devices matching a query
- name: Clear all shuns on production ASAs
  cisco.sccfm.clear_asa_shun:
    query: "name:prod-* AND connectivityState:ONLINE"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 2: Clear shuns on specific devices by UID
- name: Clear shuns on specific ASA
  cisco.sccfm.clear_asa_shun:
    uids:
      - "12345678-1234-1234-1234-123456789abc"

# Example 3: Using module_defaults (recommended)
- name: Clear shun entries
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: Clear all shuns on online ASAs
      cisco.sccfm.clear_asa_shun:
        query: "connectivityState:ONLINE"
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
    limit: int = module.params["limit"]
    offset: int = module.params["offset"]

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
        results: CdoTransaction | list[CdoCliResult] = service.clear_shun(
            device_uids=device_uids,
        )

        if isinstance(results, CdoTransaction):
            module.fail_json(
                msg=f"Clear shun failed with status: {results.cdo_transaction_status}",
                transaction_uid=results.transaction_uid,
                error_message=results.error_message,
                transaction_details=results.transaction_details,
            )

        results_data = [result.model_dump(mode="json") for result in results]
        module.exit_json(
            changed=True,
            msg=f"Successfully cleared shuns on {len(device_uids)} device(s)",
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

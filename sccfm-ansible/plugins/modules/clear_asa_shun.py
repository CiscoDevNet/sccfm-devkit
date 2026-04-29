from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException, CdoCliResult, CdoTransaction, DevicePage

from sccfm_core import ASA_DEVICE_TYPE_FILTER, AsaShunService, InventoryService, SccApiError

from ..module_utils.config import base_argument_spec, create_config

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
        **base_argument_spec(),
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
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

        if module.check_mode is True:
            module.exit_json(
                changed=True,
                msg=f"Would clear shuns on {len(device_uids)} device(s)",
                results=[],
            )
            return

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

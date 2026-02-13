from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException, CdoTransaction, DevicePage

from sccfm_core import AsaDiskFileService, InventoryService, SccApiError
from sccfm_core.models.asa_disk_file import AsaDiskFile
from sccfm_core.types import ConfigLike

from ..module_utils.config import Config

DOCUMENTATION = r"""
---
module: list_asa_disk_files
short_description: List OS and AnyConnect files on ASA device disks
description:
  - Lists files on the disk0 partition of one or more ASA devices managed by
    SCC Firewall Manager.
  - Executes C(dir disk0:) on the target devices and parses the output into
    structured data with file-type classification (OS_IMAGE, ANYCONNECT_PACKAGE,
    ASDM_IMAGE, OTHER).
  - Devices can be selected by a Lucene query or by specifying a list of UIDs.
  - See U(https://developer.cisco.com/docs/cisco-security-cloud-control/execute-cli-command/)
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
# Example 1: List files on all production ASAs matching a query
- name: List disk files on production ASAs
  cisco.sccfm.list_asa_disk_files:
    query: "name:prod-* AND connectivityState:ONLINE"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: disk_files

# Example 2: List files on specific devices by UID
- name: List disk files on specific ASAs
  cisco.sccfm.list_asa_disk_files:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
      - "87654321-4321-4321-4321-cba987654321"
  register: disk_files

# Example 3: Using module_defaults (recommended)
- name: List disk files
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: List files on branch ASAs
      cisco.sccfm.list_asa_disk_files:
        query: "name:branch-*"
      register: disk_files

    - name: Show only AnyConnect packages
      ansible.builtin.debug:
        msg: "{{ disk_files.results | selectattr('file_type', 'equalto', 'ANYCONNECT_PACKAGE') | list }}"
"""

RETURN = r"""
results:
  description: List of file entries found on the target device disks.
  returned: success
  type: list
  elements: dict
  contains:
    device_uid:
      description: The UID of the device.
      type: str
    file_name:
      description: The name of the file on disk.
      type: str
    size:
      description: The file size in bytes.
      type: int
    date:
      description: The file date and time as reported by the device.
      type: str
    file_type:
      description: Classification of the file (OS_IMAGE, ANYCONNECT_PACKAGE, ASDM_IMAGE, OTHER).
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


def _serialize_results(
    results: dict[str, list[AsaDiskFile]],
) -> list[dict[str, Any]]:
    """Convert parsed disk files into a flat list of dicts for Ansible output."""
    output: list[dict[str, Any]] = []
    for device_uid, files in results.items():
        for f in files:
            output.append(
                {
                    "device_uid": device_uid,
                    "file_name": f.name,
                    "size": f.size,
                    "date": f.date,
                    "file_type": f.file_type.value,
                }
            )
    return output


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

        disk_file_service = AsaDiskFileService(config=config)
        results = disk_file_service.list_disk_files(device_uids=device_uids)

        if isinstance(results, CdoTransaction):
            module.fail_json(
                msg=f"Disk file listing failed with status: {results.cdo_transaction_status}",
                transaction_uid=results.transaction_uid,
                error_message=results.error_message,
                transaction_details=results.transaction_details,
            )

        results_data = _serialize_results(results)
        module.exit_json(
            changed=False,
            msg=f"Successfully listed disk files on {len(device_uids)} device(s)",
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

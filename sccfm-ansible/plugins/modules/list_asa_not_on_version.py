from __future__ import annotations

import re
from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException, Device, DevicePage

from sccfm_core import ASA_DEVICE_TYPE_FILTER, InventoryService, SccApiError

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: list_asa_not_on_version
short_description: List ASA devices that are NOT running a specific software version
description:
  - Queries ASA devices managed by SCC Firewall Manager and returns only those
    that are NOT currently running the specified software version.
  - Useful for identifying devices that still need upgrading to a target version.
  - Devices can be filtered by a Lucene query or by specifying a list of UIDs.
    If neither is provided, all ASA devices are checked.
  - Version comparison is performed client-side against the C(softwareVersion)
    field returned by the inventory API.
options:
  version:
    description:
      - The target software version to check against (e.g. C(9.20(3)13)).
      - Devices NOT running this exact version will be returned.
    required: true
    type: str
  query:
    description:
      - Lucene query to narrow the set of ASA devices to check.
      - Mutually exclusive with C(uids).
      - The query is automatically combined with C(deviceType:ASA).
      - If omitted, all ASA devices are checked.
    required: false
    type: str
  uids:
    description:
      - List of device UIDs to check.
      - Mutually exclusive with C(query).
      - If omitted, all ASA devices are checked (or those matching C(query)).
    required: false
    type: list
    elements: str
  limit:
    description:
      - Maximum number of devices to fetch when using C(query) or no filter.
      - Ignored when using C(uids).
    required: false
    type: int
    default: 50
  offset:
    description:
      - Pagination offset when using C(query) or no filter.
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
# Example 1: List all ASAs not on a specific version
- name: Find ASAs not on 9.20(3)13
  cisco.sccfm.list_asa_not_on_version:
    version: "9.20(3)13"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: result

- name: Show devices that need upgrading
  ansible.builtin.debug:
    msg: "{{ item.name }} is on {{ item.software_version }}"
  loop: "{{ result.devices }}"

# Example 2: Filter by name pattern
- name: Find branch ASAs not on 9.20(3)13
  cisco.sccfm.list_asa_not_on_version:
    version: "9.20(3)13"
    query: "name:branch-*"
  register: result

# Example 3: Check specific devices by UID
- name: Check specific ASAs
  cisco.sccfm.list_asa_not_on_version:
    version: "9.20(3)13"
    uids:
      - "12345678-1234-1234-1234-123456789abc"
      - "87654321-4321-4321-4321-cba987654321"
  register: result

# Example 4: Using module_defaults (recommended)
- name: Identify devices needing upgrade
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: Find ASAs not on target version
      cisco.sccfm.list_asa_not_on_version:
        version: "9.20(3)13"
      register: result

    - name: Fail if any devices are not on target version
      ansible.builtin.fail:
        msg: "{{ result.device_count }} device(s) not on target version"
      when: result.device_count > 0
"""

RETURN = r"""
devices:
  description: List of ASA devices that are NOT running the specified version.
  returned: success
  type: list
  elements: dict
  contains:
    uid:
      description: The UID of the device.
      type: str
    name:
      description: The device name.
      type: str
    software_version:
      description: The current software version running on the device.
      type: str
    asdm_version:
      description: The current ASDM version running on the device.
      type: str
    connectivity_state:
      description: The device connectivity state.
      type: str
    config_state:
      description: The device configuration state.
      type: str
device_count:
  description: Number of devices not on the specified version.
  returned: success
  type: int
matched_device_count:
  description: Number of ASA devices matched before version comparison.
  returned: success
  type: int
"""

_VERSION_RE = re.compile(r"^\d+\.\d+")


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        **base_argument_spec(),
        "version": {"type": "str", "required": True},
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
    }


def _validate_version(module: AnsibleModule, version: str) -> None:
    if not _VERSION_RE.match(version):
        module.fail_json(
            msg=(
                f"Invalid version format: '{version}'. "
                "Expected Cisco format like '9.20(3)13' or '9.18.4'."
            )
        )


def _fetch_devices(module: AnsibleModule) -> list[Device]:
    config = create_config(module)
    inventory_service = InventoryService(config=config)

    uids: list[str] | None = module.params.get("uids")
    query: str | None = module.params.get("query")
    limit: int = module.params["limit"]
    offset: int = module.params["offset"]

    if uids:
        uid_query = " OR ".join(f"uid:{uid}" for uid in uids)
        page: DevicePage = inventory_service.get_devices(limit=len(uids), offset=0, query=uid_query)
    elif query:
        page = inventory_service.get_devices(
            limit=limit,
            offset=offset,
            query=f"({query}) AND {ASA_DEVICE_TYPE_FILTER}",
        )
    else:
        page = inventory_service.get_devices(
            limit=limit,
            offset=offset,
            query=ASA_DEVICE_TYPE_FILTER,
        )

    return cast(list[Device], page.items or [])


def _serialize_device(device: Device) -> dict[str, Any]:
    return {
        "uid": device.uid,
        "name": device.name,
        "software_version": device.software_version,
        "asdm_version": device.asdm_version,
        "connectivity_state": (
            device.connectivity_state.value if device.connectivity_state else None
        ),
        "config_state": device.config_state.value if device.config_state else None,
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[["query", "uids"]],
        supports_check_mode=True,
    )

    version: str = module.params["version"]
    _validate_version(module, version)

    try:
        all_devices = _fetch_devices(module)
        matched_device_count = len(all_devices)

        if matched_device_count == 0:
            query: str | None = module.params.get("query")
            uids: list[str] | None = module.params.get("uids")
            if query or uids:
                msg = "No ASA devices matched the specified filter."
            else:
                msg = "No ASA devices found."
            module.exit_json(
                changed=False,
                msg=msg,
                devices=[],
                device_count=0,
                matched_device_count=0,
            )

        devices_not_on_version = [d for d in all_devices if d.software_version != version]
        serialized = [_serialize_device(d) for d in devices_not_on_version]
        count = len(serialized)

        if count == 0:
            msg = f"All {matched_device_count} matched device(s) are on version {version}."
        else:
            msg = (
                f"Found {count} device(s) not on version {version} "
                f"out of {matched_device_count} matched device(s)."
            )

        module.exit_json(
            changed=False,
            msg=msg,
            devices=serialized,
            device_count=count,
            matched_device_count=matched_device_count,
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

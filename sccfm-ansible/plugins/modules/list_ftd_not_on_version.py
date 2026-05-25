# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException, Device, DevicePage, EntityType, FtdVersion

from sccfm_core import FTD_DEVICE_TYPE_FILTER, InventoryService, SccApiError
from sccfm_core.models.ftd_upgrade_version import FtdGroupCompatibleVersions
from sccfm_core.services.inventory import FtdUpgradeVersionService

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: list_ftd_not_on_version
short_description: List FTD devices that are NOT running a specific or recommended software version
description:
  - Queries FTD devices managed by SCC Firewall Manager and returns only those
    that are NOT currently running the specified or recommended software version.
  - Use C(version) to check against a specific version string, or C(recommended)
    to check each device against its Cisco-suggested upgrade version.
  - Devices can be filtered by a Lucene query or by specifying a list of UIDs.
    If neither is provided, all FTD devices are checked.
  - In C(version) mode, comparison is performed client-side against the
    C(softwareVersion) field returned by the inventory API.
  - In C(recommended) mode, the compatible-versions API is called per device to
    determine the suggested version.
options:
  version:
    description:
      - The target software version to check against (e.g. C(7.4.1)).
      - Devices NOT running this exact version will be returned.
      - Mutually exclusive with C(recommended).
    required: false
    type: str
  recommended:
    description:
      - When true, check each device against its Cisco-recommended (suggested)
        upgrade version instead of a fixed version string.
      - Mutually exclusive with C(version).
    required: false
    type: bool
    default: false
  query:
    description:
      - Lucene query to narrow the set of FTD devices to check.
      - Mutually exclusive with C(uids).
      - The query is automatically combined with FTD device type filters.
      - If omitted, all FTD devices are checked.
    required: false
    type: str
  uids:
    description:
      - List of device UIDs to check.
      - Mutually exclusive with C(query).
      - If omitted, all FTD devices are checked (or those matching C(query)).
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
# Example 1: List all FTDs not on a specific version
- name: Find FTDs not on 7.4.1
  cisco.sccfm.list_ftd_not_on_version:
    version: "7.4.1"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: result

- name: Show devices that need upgrading
  ansible.builtin.debug:
    msg: "{{ item.name }} is on {{ item.software_version }}"
  loop: "{{ result.devices }}"

# Example 2: Check against the recommended version
- name: Find FTDs not on recommended version
  cisco.sccfm.list_ftd_not_on_version:
    recommended: true
  register: result

- name: Show non-compliant devices
  ansible.builtin.debug:
    msg: "{{ item.name }} is on {{ item.software_version }}, recommended: {{ item.recommended_version }}"
  loop: "{{ result.devices }}"

# Example 3: Filter by name pattern
- name: Find branch FTDs not on 7.4.1
  cisco.sccfm.list_ftd_not_on_version:
    version: "7.4.1"
    query: "name:branch-*"
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
    - name: Find FTDs not on target version
      cisco.sccfm.list_ftd_not_on_version:
        version: "7.4.1"
      register: result

    - name: Fail if any devices are not on target version
      ansible.builtin.fail:
        msg: "{{ result.device_count }} device(s) not on target version"
      when: result.device_count > 0
"""

RETURN = r"""
devices:
  description: List of FTD devices that are NOT running the specified or recommended version.
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
    recommended_version:
      description: The Cisco-recommended version for this device (only in recommended mode).
      type: str
    connectivity_state:
      description: The device connectivity state.
      type: str
    config_state:
      description: The device configuration state.
      type: str
device_count:
  description: Number of devices not on the specified or recommended version.
  returned: success
  type: int
matched_device_count:
  description: Number of FTD devices matched before version comparison.
  returned: success
  type: int
skipped:
  description: Devices that could not be evaluated (only in recommended mode).
  returned: success (recommended mode only, when devices were skipped)
  type: dict
mode:
  description: The evaluation mode used (C(specified) or C(recommended)).
  returned: success
  type: str
"""

_VERSION_RE = re.compile(r"^\d+\.\d+")


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        **base_argument_spec(),
        "version": {"type": "str", "required": False},
        "recommended": {"type": "bool", "required": False, "default": False},
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
    }


def _validate_mode(module: AnsibleModule) -> None:
    version: str | None = module.params.get("version")
    recommended: bool = module.params.get("recommended", False)

    if version and recommended:
        module.fail_json(msg="Provide either 'version' or 'recommended', not both.")
    if not version and not recommended:
        module.fail_json(msg="Provide one of 'version' or 'recommended'.")
    if version and not _VERSION_RE.match(version):
        module.fail_json(
            msg=(
                f"Invalid version format: '{version}'. " "Expected format like '7.4.1' or '7.2.0'."
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
            query=f"({query}) AND {FTD_DEVICE_TYPE_FILTER}",
        )
    else:
        page = inventory_service.get_devices(
            limit=limit,
            offset=offset,
            query=FTD_DEVICE_TYPE_FILTER,
        )

    return cast(list[Device], page.items or [])


def _serialize_device(device: Device, *, recommended_version: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "uid": device.uid,
        "name": device.name,
        "software_version": device.software_version,
        "connectivity_state": (
            device.connectivity_state.value if device.connectivity_state else None
        ),
        "config_state": device.config_state.value if device.config_state else None,
    }
    if recommended_version is not None:
        result["recommended_version"] = recommended_version
    return result


def _check_recommended(
    module: AnsibleModule,
    devices: list[Device],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    config = create_config(module)
    device_uids = [d.uid for d in devices]
    if not device_uids:
        return [], {}

    upgrade_service = FtdUpgradeVersionService(config=config)
    results = upgrade_service.get_compatible_versions(device_uids=device_uids)

    not_on_version: list[dict[str, Any]] = []
    skipped: dict[str, str] = dict(results.skipped)

    for device in devices:
        if device.uid in results.skipped:
            continue

        compatible = results.per_device.get(device.uid, [])
        suggested = next((v for v in compatible if v.is_suggested_version), None)

        if suggested is None:
            skipped[device.uid] = "No recommended version available"
            continue

        if device.software_version != suggested.software_version:
            not_on_version.append(
                _serialize_device(device, recommended_version=suggested.software_version)
            )

    return not_on_version, skipped


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[["query", "uids"], ["version", "recommended"]],
        supports_check_mode=True,
    )

    _validate_mode(module)

    version: str | None = module.params.get("version")
    recommended: bool = module.params.get("recommended", False)
    mode = "recommended" if recommended else "specified"

    try:
        all_devices = _fetch_devices(module)
        matched_device_count = len(all_devices)

        if recommended:
            serialized, skipped = _check_recommended(module, all_devices)
            evaluated_count = matched_device_count - len(skipped)
        else:
            devices_not_on_version = [d for d in all_devices if d.software_version != version]
            serialized = [_serialize_device(d) for d in devices_not_on_version]
            skipped = {}
            evaluated_count = matched_device_count

        count = len(serialized)

        if matched_device_count == 0:
            query: str | None = module.params.get("query")
            uids: list[str] | None = module.params.get("uids")
            msg = (
                "No FTD devices matched the specified filter."
                if query or uids
                else "No FTD devices found."
            )
        elif evaluated_count == 0:
            msg = (
                f"All {matched_device_count} matched device(s) were skipped; "
                "none could be evaluated."
            )
        elif count == 0:
            version_label = "their recommended version" if recommended else f"version {version}"
            msg = f"All {evaluated_count} evaluated device(s) are on {version_label}."
        else:
            version_label = "their recommended version" if recommended else f"version {version}"
            msg = (
                f"Found {count} device(s) not on {version_label} "
                f"out of {evaluated_count} evaluated device(s)."
            )

        result: dict[str, Any] = {
            "changed": False,
            "msg": msg,
            "mode": mode,
            "devices": serialized,
            "device_count": count,
            "matched_device_count": matched_device_count,
        }
        if recommended and skipped:
            result["skipped"] = skipped

        module.exit_json(**result)

    except ApiException as e:
        error = SccApiError.from_exception(e)
        module.fail_json(**error.to_dict())
    except Exception as e:
        module.fail_json(msg=f"Unexpected error: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import (
    ApiException,
    DevicePage,
    EntityType,
    FtdVersion,
)

from sccfm_core import FTD_DEVICE_TYPE_FILTER, InventoryService, SccApiError
from sccfm_core.models.ftd_upgrade_version import FtdGroupCompatibleVersions
from sccfm_core.services.inventory import FtdUpgradeVersionService
from sccfm_core.types import ConfigLike

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: list_ftd_compatible_versions
short_description: List software versions compatible with a group of FTD devices
description:
  - Queries compatible upgrade versions for one or more FTD devices managed by
    SCC Firewall Manager and computes the intersection of versions common to
    all selected devices.
  - Returns version details including software version, upgrade package UID,
    upgrade type (UPGRADE, PATCH, HOTFIX), and whether the version is the
    suggested upgrade target.
options:
  query:
    description:
      - Lucene query to filter FTD devices.
      - Mutually exclusive with C(uids).
      - The query is automatically combined with FTD device type filters.
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
  per_device:
    description:
      - Whether to include per-device version breakdown in the output.
      - When false (default), single-device queries return a flat list and
        multi-device queries return only the common versions.
      - When true, the full per-device breakdown is included alongside
        common versions.
    required: false
    type: bool
    default: false
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
# Example 1: Get compatible versions for a single FTD (flat list output)
- name: Get compatible versions for a single FTD
  cisco.sccfm.list_ftd_compatible_versions:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: compat_versions

- name: Show compatible versions
  ansible.builtin.debug:
    var: compat_versions.compatible_versions

# Example 2: Get common versions across a group (intersection)
- name: Get common compatible versions for specific FTDs
  cisco.sccfm.list_ftd_compatible_versions:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
      - "87654321-4321-4321-4321-cba987654321"
  register: compat_versions

- name: Show common versions
  ansible.builtin.debug:
    var: compat_versions.common_versions

# Example 3: Include per-device breakdown (opt-in)
- name: Get group versions with per-device details
  cisco.sccfm.list_ftd_compatible_versions:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
      - "87654321-4321-4321-4321-cba987654321"
    per_device: true
  register: compat_versions

- name: Show per-device counts
  ansible.builtin.debug:
    msg: "Device {{ item.key }}: {{ item.value | length }} version(s)"
  loop: "{{ compat_versions.per_device | dict2items }}"

# Example 4: Using module_defaults (recommended)
- name: List FTD compatible versions
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: Get compatible versions for branch FTDs
      cisco.sccfm.list_ftd_compatible_versions:
        query: "name:branch-*"
      register: compat_versions
"""

RETURN = r"""
compatible_versions:
  description: >-
    Flat list of compatible versions. Returned for single-device queries
    when C(per_device) is false.
  returned: success (single device, per_device=false)
  type: list
  elements: dict
common_versions:
  description: >-
    Software versions compatible with every selected FTD device. Returned
    for multi-device queries or when C(per_device) is true.
  returned: success (multi-device or per_device=true)
  type: list
  elements: dict
per_device:
  description: Per-device compatible version lists keyed by device UID.
  returned: success (only when per_device=true)
  type: dict
device_count:
  description: Number of devices included in the query.
  returned: success (multi-device or per_device=true)
  type: int
skipped:
  description: FTD device UIDs skipped during eligibility checks, keyed by UID.
  returned: success (check mode or when devices are skipped)
  type: dict
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
        "per_device": {"type": "bool", "required": False, "default": False},
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
        query=f"({query}) AND {FTD_DEVICE_TYPE_FILTER}",
    )
    return [device.uid for device in (page.items or [])]


def _version_to_dict(v: FtdVersion) -> dict[str, Any]:
    return {
        "software_version": v.software_version,
        "upgrade_package_uid": v.upgrade_package_uid,
        "upgrade_type": v.upgrade_type,
        "is_suggested_version": v.is_suggested_version,
        "filename": v.filename,
    }


def _serialize_results(
    results: FtdGroupCompatibleVersions,
    *,
    is_single: bool,
    show_per_device: bool,
) -> dict[str, Any]:
    if is_single and not show_per_device:
        uid = next(iter(results.per_device))
        versions = results.per_device[uid]
        return {
            "compatible_versions": [_version_to_dict(v) for v in versions],
        }

    output: dict[str, Any] = {
        "common_versions": [_version_to_dict(v) for v in results.common_versions],
        "device_count": len(results.per_device),
    }
    if show_per_device:
        output["per_device"] = {
            uid: [_version_to_dict(v) for v in versions]
            for uid, versions in results.per_device.items()
        }
    return output


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[["query", "uids"]],
        required_one_of=[["query", "uids"]],
        supports_check_mode=True,
    )

    if module.check_mode is True:
        output: dict[str, Any] = {
            "changed": False,
            "msg": "Check mode: compatible-version lookup would run against the selected FTD devices.",
            "compatible_versions": [],
            "common_versions": [],
            "device_count": 0,
            "skipped": {},
        }
        if module.params.get("per_device", False):
            output["per_device"] = {}
        module.exit_json(**output)

    config = create_config(module)

    query: str | None = module.params.get("query")
    uids: list[str] | None = module.params.get("uids")
    limit: int = module.params["limit"]
    offset: int = module.params["offset"]
    show_per_device: bool = module.params.get("per_device", False)

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

        upgrade_service = FtdUpgradeVersionService(config=config)
        results = upgrade_service.get_compatible_versions(device_uids=device_uids)

        for uid, reason in results.skipped.items():
            module.warn(f"Skipping device {uid}: {reason}")

        if not results.per_device:
            module.fail_json(msg="No devices returned compatible versions.")

        eligible_count = len(results.per_device)
        is_single = eligible_count == 1
        serialized = _serialize_results(
            results, is_single=is_single, show_per_device=show_per_device
        )

        if is_single and not show_per_device:
            version_count = len(serialized.get("compatible_versions", []))
            msg = f"Found {version_count} compatible version(s)"
        else:
            msg = (
                f"Found {len(results.common_versions)} common compatible "
                f"version(s) across {eligible_count} device(s)"
            )

        module.exit_json(changed=False, msg=msg, **serialized)

    except ApiException as e:
        error = SccApiError.from_exception(e)
        module.fail_json(**error.to_dict())
    except Exception as e:
        module.fail_json(msg=f"Unexpected error: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

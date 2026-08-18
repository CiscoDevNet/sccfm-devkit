# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException, CdoTransaction, DevicePage

    from cisco_sccfm_core import (
        ASA_DEVICE_TYPE_FILTER,
        AsaBootRegistryService,
        InventoryService,
        SccApiError,
    )
    from cisco_sccfm_core.models.asa_boot_registry import AsaBootRegistry
    from cisco_sccfm_core.types import ConfigLike
except ImportError as exc:
    record_import_error(exc)
    ApiException = NotFoundError = FtdConfigureManagerError = RuntimeError


from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: list_asa_boot_registry
short_description: Show boot registry info for ASA devices
description:
  - Retrieves boot registry information (system image, config register,
    boot system entries) from one or more ASA devices managed by
    SCC Firewall Manager.
  - Executes C(show version) and C(show run boot) on the target devices and
    parses the output into structured data.
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
  profile:
    description: Named SCCFM profile configured by C(sccfm-cli configure).
    required: false
    type: str
    default: default
  config_path:
    description: Optional path to the canonical SCCFM profile configuration file.
    required: false
    type: path
author:
  - Cisco SCCFM Team
"""

EXAMPLES = r"""
# Example 1: Get boot registry info for ASAs matching a query
- name: List boot registry on production ASAs
  cisco.sccfm.list_asa_boot_registry:
    query: "name:prod-* AND connectivityState:ONLINE"
    profile: default
  register: boot_registry

# Example 2: Get boot registry info for specific devices by UID
- name: List boot registry on specific ASAs
  cisco.sccfm.list_asa_boot_registry:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
      - "87654321-4321-4321-4321-cba987654321"
  register: boot_registry

# Example 3: Using module_defaults (recommended)
- name: List boot registry
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: List boot registry on branch ASAs
      cisco.sccfm.list_asa_boot_registry:
        query: "name:branch-*"
      register: boot_registry

    - name: Show devices with modified config
      ansible.builtin.debug:
        msg: "{{ boot_registry.results | selectattr('config_modified', 'equalto', true) | list }}"
"""

RETURN = r"""
results:
  description: List of boot registry entries for the target devices.
  returned: success
  type: list
  elements: dict
  contains:
    device_uid:
      description: The UID of the device.
      type: str
    system_image_file:
      description: The system image file path on the device.
      type: str
    compiled_date:
      description: The date the running image was compiled.
      type: str
    config_register:
      description: The configuration register value (e.g. 0x1).
      type: str
    config_modified:
      description: Whether the configuration has been modified since last restart.
      type: bool
    boot_system_entries:
      description: List of boot system entries from the running config.
      type: list
      elements: str
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
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


def _serialize_results(
    results: dict[str, AsaBootRegistry],
) -> list[dict[str, Any]]:
    """Convert parsed boot registry data into a flat list of dicts for Ansible output."""
    output: list[dict[str, Any]] = []
    for device_uid, boot in results.items():
        output.append(
            {
                "device_uid": device_uid,
                "system_image_file": boot.system_image_file,
                "compiled_date": boot.compiled_date,
                "config_register": boot.config_register,
                "config_modified": boot.config_modified,
                "boot_system_entries": boot.boot_system_entries,
            }
        )
    return output


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[["query", "uids"]],
        required_one_of=[["query", "uids"]],
        supports_check_mode=True,
    )

    config: Config = create_config(module)
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

        boot_registry_service = AsaBootRegistryService(config=config)
        results = boot_registry_service.list_boot_registry(device_uids=device_uids)

        if isinstance(results, CdoTransaction):
            module.fail_json(
                msg=f"Boot registry retrieval failed with status: {results.cdo_transaction_status}",
                transaction_uid=results.transaction_uid,
                error_message=results.error_message,
                transaction_details=results.transaction_details,
            )

        results_data = _serialize_results(results)
        module.exit_json(
            changed=False,
            msg=f"Successfully retrieved boot registry from {len(device_uids)} device(s)",
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

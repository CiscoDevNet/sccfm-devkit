# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import (
    ApiException,
    CdoTransaction,
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
)

from sccfm_core import ASA_DEVICE_TYPE_FILTER, InventoryService, SccApiError
from sccfm_core.models.asa_boot_image_change_result import AsaBootImageChangeResult
from sccfm_core.services.inventory import AsaBootImageService
from sccfm_core.utils import validate_asa_image_path

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: change_asa_boot_image
short_description: Change the configured boot image on ASA devices
description:
  - Changes the configured ASA boot image for the next reload.
  - The requested image must already exist on the device filesystem.
  - Check mode validates the image path and inspects the containing filesystem
    without changing the boot configuration.
  - The module persists the boot configuration and verifies the resulting
    C(boot system) entry.
  - The module does not upload the image and does not reload the device.
  - Devices can be selected by a Lucene query or by specifying a list of UIDs.
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
      - List of device UIDs to target.
      - Mutually exclusive with C(query).
    required: false
    type: list
    elements: str
  image_path:
    description:
      - Full ASA image path already present on the device, such as
        C(disk0:/asa9xxx.bin) or C(boot:/asa9xxx.bin).
    required: true
    type: str
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
# Example 1: Change boot image using a query
- name: Change ASA boot image for branch devices
  cisco.sccfm.change_asa_boot_image:
    query: "name:branch-*"
    image_path: "disk0:/asa9-18-4-smp-k8.bin"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 2: Change boot image on specific devices
- name: Change boot image on specific ASA devices
  cisco.sccfm.change_asa_boot_image:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
      - "87654321-4321-4321-4321-cba987654321"
    image_path: "boot:/asa9231-smp-k8.bin"

# Example 3: Check mode
- name: Preview boot image changes
  cisco.sccfm.change_asa_boot_image:
    query: "name:prod-*"
    image_path: "disk0:/asa9-18-4-smp-k8.bin"
    # check_mode runs non-mutating pre-checks, including image path validation
    # on the device and containing-filesystem inspection.
  check_mode: true

# Example 4: Using module_defaults (recommended)
- name: Change ASA boot image
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: Set boot image on branch ASAs
      cisco.sccfm.change_asa_boot_image:
        query: "name:branch-*"
        image_path: "disk0:/asa9-18-4-smp-k8.bin"
"""

RETURN = r"""
results:
  description: List of boot image change results, one per matched device.
  returned: success
  type: list
  elements: dict
  contains:
    device_name:
      description: Device name.
      type: str
    device_uid:
      description: Device UID.
      type: str
    requested_image_path:
      description: Requested on-device image path.
      type: str
    status:
      description: Outcome of the operation.
      type: str
    message:
      description: Human-readable result message.
      type: str
    boot_system_entries_before:
      description: Boot entries before the operation.
      type: list
      elements: str
    boot_system_entries_after:
      description: Boot entries after the operation.
      type: list
      elements: str
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        **base_argument_spec(),
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "image_path": {"type": "str", "required": True},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
    }


def _resolve_devices(
    config: Config,
    *,
    query: str | None,
    uids: list[str] | None,
    limit: int,
    offset: int,
) -> list[Device]:
    inventory_service = InventoryService(config=config)
    if uids:
        uid_query = " OR ".join([f'uid:"{uid}"' for uid in uids])
        page: DevicePage = inventory_service.get_devices(
            limit=max(limit, len(uids)),
            offset=0,
            query=f"({uid_query}) AND {ASA_DEVICE_TYPE_FILTER}",
        )
        return list(page.items or [])

    page = inventory_service.get_devices(
        limit=limit,
        offset=offset,
        query=f"({cast(str, query)}) AND {ASA_DEVICE_TYPE_FILTER}",
    )
    return list(page.items or [])


def _device_attr(device: Device, snake_name: str, camel_name: str) -> Any:
    return getattr(device, snake_name, getattr(device, camel_name, None))


def _state_text(state: Any) -> str:
    if state is None:
        return "unknown"
    return str(getattr(state, "value", state))


def _is_device_ready(device: Device) -> bool:
    connectivity = _state_text(_device_attr(device, "connectivity_state", "connectivityState"))
    config_state = _state_text(_device_attr(device, "config_state", "configState"))
    return (
        connectivity == ConnectivityState.ONLINE.value and config_state == ConfigState.SYNCED.value
    )


def _device_not_ready_result(device: Device, image_path: str) -> AsaBootImageChangeResult:
    connectivity = _state_text(_device_attr(device, "connectivity_state", "connectivityState"))
    config_state = _state_text(_device_attr(device, "config_state", "configState"))
    return AsaBootImageChangeResult(
        device_uid=device.uid,
        requested_image_path=image_path,
        status="device_not_ready",
        message=(
            "Device is not ready for config mutation "
            f"(connectivity_state={connectivity}, config_state={config_state})."
        ),
        boot_system_entries_before=[],
        boot_system_entries_after=[],
    )


def _serialize_result(device: Device, result: AsaBootImageChangeResult) -> dict[str, Any]:
    return {
        "device_name": device.name,
        "device_uid": result.device_uid,
        "requested_image_path": result.requested_image_path,
        "status": result.status,
        "message": result.message,
        "boot_system_entries_before": result.boot_system_entries_before,
        "boot_system_entries_after": result.boot_system_entries_after,
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[["query", "uids"]],
        required_one_of=[["query", "uids"]],
        supports_check_mode=True,
    )

    config = create_config(module)

    query: str | None = module.params.get("query")
    uids: list[str] | None = module.params.get("uids")
    image_path: str = module.params["image_path"]
    limit: int = module.params["limit"]
    offset: int = module.params["offset"]

    try:
        validate_asa_image_path(image_path)
    except ValueError as exc:
        module.fail_json(msg=str(exc))

    try:
        devices = _resolve_devices(config, query=query, uids=uids, limit=limit, offset=offset)
        if not devices:
            module.fail_json(msg="No devices found matching the specified query.")

        ready_devices = [device for device in devices if _is_device_ready(device)]
        ready_uids = [device.uid for device in ready_devices]
        uid_to_device = {device.uid: device for device in devices}
        merged_results: dict[str, AsaBootImageChangeResult] = {
            device.uid: _device_not_ready_result(device, image_path)
            for device in devices
            if device.uid not in ready_uids
        }

        if ready_devices:
            boot_image_service = AsaBootImageService(config=config)
            service_results = (
                boot_image_service.check_boot_image(device_uids=ready_uids, image_path=image_path)
                if module.check_mode
                else boot_image_service.change_boot_image(
                    device_uids=ready_uids, image_path=image_path
                )
            )

            if isinstance(service_results, CdoTransaction):
                module.fail_json(
                    msg=f"Boot image change failed with status: {service_results.cdo_transaction_status}",
                    transaction_uid=service_results.transaction_uid,
                    error_message=service_results.error_message,
                    transaction_details=service_results.transaction_details,
                )

            merged_results.update(service_results)

        ordered_results = [
            _serialize_result(uid_to_device[device.uid], merged_results[device.uid])
            for device in devices
        ]
        changed_status = "would_change" if module.check_mode else "success"
        changed = any(result["status"] == changed_status for result in ordered_results)

        module.exit_json(
            changed=changed,
            msg=f"Processed boot image change for {len(devices)} device(s)",
            results=ordered_results,
        )

    except ApiException as e:
        error = SccApiError.from_exception(e)
        module.fail_json(**error.to_dict())
    except ValueError as e:
        module.fail_json(msg=str(e))
    except Exception as e:
        module.fail_json(msg=f"Unexpected error: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

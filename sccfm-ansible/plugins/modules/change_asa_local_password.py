# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0
# flake8: noqa: E402
# isort: skip_file

from __future__ import annotations

DOCUMENTATION = r"""
---
module: change_asa_local_password
short_description: Change a local user password on ASA devices
description:
  - Changes the local user password on one or more ASA devices managed by
    SCC Firewall Manager.
  - The module performs a pre-check to confirm the user exists, applies the
    password command, and verifies the user is still present afterward.
  - Devices can be selected by a Lucene query or by specifying a list of UIDs.
  - The query uses the same syntax as the Get Devices API.
  - See U(https://developer.cisco.com/docs/cisco-security-cloud-control-firewall-manager/get-devices/)
    for query documentation.
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
  username:
    description:
      - The local ASA username whose password will be changed.
    required: true
    type: str
  new_password:
    description:
      - The new password to set for the user.
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
  api_token:
    description: API token for SCCFM.
    required: false
    type: str
author:
  - huides00 (@huides00)
  - Scoombe (@Scoombe)
  - afercal (@afercal)
"""

EXAMPLES = r"""
# Example 1: Change password on ASAs matching a query
- name: Change admin password on branch ASAs
  cisco.sccfm.change_asa_local_password:
    query: "name:branch-* AND connectivityState:ONLINE"
    username: admin
    new_password: "{{ vault_new_asa_password }}"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: password_results

# Example 2: Change password on specific devices by UID
- name: Change admin password on specific ASAs
  cisco.sccfm.change_asa_local_password:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
      - "87654321-4321-4321-4321-cba987654321"
    username: admin
    new_password: "{{ vault_new_asa_password }}"
  register: password_results

# Example 3: Using module_defaults (recommended)
- name: Change passwords
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: Change admin password on all online ASAs
      cisco.sccfm.change_asa_local_password:
        query: "connectivityState:ONLINE"
        username: admin
        new_password: "{{ vault_new_asa_password }}"
      register: password_results

    - name: Show results
      ansible.builtin.debug:
        msg: "{{ item.device_uid }}: {{ item.status }} - {{ item.message }}"
      loop: "{{ password_results.results }}"
      loop_control:
        label: "{{ item.device_uid }}"
"""

RETURN = r"""
results:
  description: List of password change results, one per target device.
  returned: success
  type: list
  elements: dict
  contains:
    device_uid:
      description: The UID of the device.
      type: str
    status:
      description: >
        The outcome of the password change attempt.
        One of success, failed, or user_not_found.
      type: str
    message:
      description: Human-readable description of the outcome.
      type: str
"""


from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.config import Config, base_argument_spec, create_config
from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException, CdoTransaction, DevicePage

    from cisco_sccfm_core import ASA_DEVICE_TYPE_FILTER, InventoryService, SccApiError
    from cisco_sccfm_core.models.asa_password_change_result import AsaPasswordChangeResult
    from cisco_sccfm_core.services.inventory.asa_user_password_service import AsaUserPasswordService
    from cisco_sccfm_core.types import ConfigLike
except ImportError as exc:
    record_import_error(exc)


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "username": {"type": "str", "required": True},
        "new_password": {"type": "str", "required": True, "no_log": True},
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
    results: dict[str, AsaPasswordChangeResult],
) -> list[dict[str, str]]:
    """Convert password change results into a list of dicts for Ansible output."""
    output: list[dict[str, str]] = []
    for device_uid, result in results.items():
        output.append(
            {
                "device_uid": device_uid,
                "status": result.status,
                "message": result.message,
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
    username: str = module.params["username"]
    new_password: str = module.params["new_password"]
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

        if module.check_mode is True:
            module.exit_json(
                changed=True,
                msg=f"Would change password for user '{username}' on {len(device_uids)} device(s)",
                results=[],
            )
            return

        password_service = AsaUserPasswordService(config=config)
        results = password_service.change_password(
            device_uids=device_uids,
            username=username,
            new_password=new_password,
        )

        if isinstance(results, CdoTransaction):
            module.fail_json(
                msg=f"Password change failed with status: {results.cdo_transaction_status}",
                transaction_uid=results.transaction_uid,
                error_message=results.error_message,
                transaction_details=results.transaction_details,
            )

        results_data = _serialize_results(results)
        module.exit_json(
            changed=True,
            msg=f"Password change completed on {len(device_uids)} device(s)",
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

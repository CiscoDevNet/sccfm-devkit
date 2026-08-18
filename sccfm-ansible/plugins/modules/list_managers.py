# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

DOCUMENTATION = r"""
---
module: list_managers
short_description: List FMC managers in SCC Firewall Manager
description:
  - List on-premises and cloud-delivered FMC managers in your SCC Firewall Manager tenant.
  - Supports pagination via C(limit) and C(offset).
  - Supports Lucene query filtering via C(query).
options:
  query:
    description: Optional Lucene query string to filter results (e.g. C(name:myFMC*)).
    required: false
    type: str
  limit:
    description: Maximum number of results to return.
    required: false
    type: int
    default: 50
  offset:
    description: Pagination offset (number of results to skip).
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
  - Cisco SCCFM Team (@CiscoDevNet)
"""

EXAMPLES = r"""
# Example 1: List all managers
- name: List all managers
  cisco.sccfm.list_managers:
    profile: default
  register: result

- name: Show managers
  ansible.builtin.debug:
    var: result.managers

# Example 2: Find a specific manager by name
- name: Find cdFMC manager
  cisco.sccfm.list_managers:
    query: "name:mycdFMC"
  register: result

- name: Get domain UID
  ansible.builtin.set_fact:
    domain_uid: "{{ result.managers[0].fmc_domain_uid }}"

# Example 3: Using module_defaults (recommended)
- name: List managers
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: List all managers
      cisco.sccfm.list_managers:
        limit: 50
"""

RETURN = r"""
managers:
  description: List of managers returned by the API.
  returned: success
  type: list
  elements: dict
  contains:
    uid:
      description: Unique identifier of the manager.
      type: str
    name:
      description: Name of the manager.
      type: str
    device_type:
      description: Type of the manager (e.g. CDFMC, ONPREM_FMC).
      type: str
    fmc_domain_uid:
      description: The FMC domain UID. Pass this to list_cdfmc_access_policies.
      type: str
    connectivity_state:
      description: Connectivity state of the manager.
      type: str
    software_version:
      description: Software version of the manager.
      type: str
count:
  description: Total number of matching managers.
  returned: success
  type: int
limit:
  description: The limit used in the request.
  returned: success
  type: int
offset:
  description: The offset used in the request.
  returned: success
  type: int
"""


from typing import Any

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException, DevicePage

    from cisco_sccfm_core import SccApiError
    from cisco_sccfm_core.services.inventory import InventoryService
except ImportError as exc:
    record_import_error(exc)
    ApiException = RuntimeError
    NotFoundError = LookupError
    FtdConfigureManagerError = ValueError


from ..module_utils.config import base_argument_spec, create_config


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "query": {"type": "str", "required": False, "default": None},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config = create_config(module)

    try:
        service = InventoryService(config)
        page: DevicePage = service.get_managers(
            limit=module.params["limit"],
            offset=module.params["offset"],
            query=module.params.get("query"),
        )
        managers = [
            {
                "uid": d.uid,
                "name": d.name,
                "device_type": d.device_type,
                "fmc_domain_uid": d.fmc_domain_uid,
                "connectivity_state": d.connectivity_state,
                "software_version": d.software_version,
            }
            for d in (page.items or [])
        ]
        module.exit_json(
            changed=False,
            managers=managers,
            count=page.count or 0,
            limit=module.params["limit"],
            offset=module.params["offset"],
        )
    except ApiException as e:
        error = SccApiError.from_exception(e)
        module.fail_json(**error.to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to list managers: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

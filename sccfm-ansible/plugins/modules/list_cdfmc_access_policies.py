# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0
# flake8: noqa: E402
# isort: skip_file

from __future__ import annotations

DOCUMENTATION = r"""
---
module: list_cdfmc_access_policies
short_description: List FMC access policies for a cdFMC domain
description:
  - List access policies available on the cloud-delivered FMC for a given domain.
  - Use C(list_managers) first to obtain the C(fmc_domain_uid) of the cdFMC.
options:
  domain_uid:
    description: >-
      The FMC domain UID to query. Obtain this from the C(fmc_domain_uid) field
      returned by the C(list_managers) module.
    required: true
    type: str
  limit:
    description: Maximum number of access policies to return.
    required: false
    type: int
    default: 50
  offset:
    description: Pagination offset.
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
# Example 1: List access policies for a domain
- name: List cdFMC access policies
  cisco.sccfm.list_cdfmc_access_policies:
    domain_uid: "e276abec-e0f2-11e3-8169-6d9ed49b625f"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: result

- name: Show access policies
  ansible.builtin.debug:
    var: result.access_policies

# Example 2: Using module_defaults (recommended)
- name: List cdFMC access policies
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: List access policies for a domain
      cisco.sccfm.list_cdfmc_access_policies:
        domain_uid: "e276abec-e0f2-11e3-8169-6d9ed49b625f"
        limit: 50
        offset: 0
"""

RETURN = r"""
access_policies:
  description: List of FMC access policies in the given domain.
  returned: success
  type: list
  elements: dict
  contains:
    uid:
      description: Unique identifier of the access policy. Use as C(fmc_access_policy_uid).
      type: str
    name:
      description: Name of the access policy.
      type: str
count:
  description: Number of access policies returned.
  returned: success
  type: int
limit:
  description: Maximum number of access policies requested.
  returned: success
  type: int
offset:
  description: Pagination offset requested.
  returned: success
  type: int
"""


from typing import Any

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.config import base_argument_spec, create_config
from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException

    from cisco_sccfm_core import SccApiError
    from cisco_sccfm_core.services.inventory.cdfmc_access_policy_service import (
        CdfmcAccessPolicyService,
    )
except ImportError as exc:
    record_import_error(exc)


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "domain_uid": {"type": "str", "required": True},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    limit = module.params["limit"]
    offset = module.params["offset"]

    config = create_config(module)

    try:
        service = CdfmcAccessPolicyService(config)
        page = service.get_access_policies(
            module.params["domain_uid"],
            limit=limit,
            offset=offset,
        )
        access_policies = [{"uid": p.uid, "name": p.name} for p in page.items]
        module.exit_json(
            changed=False,
            access_policies=access_policies,
            count=page.count,
            limit=page.limit,
            offset=page.offset,
        )
    except ApiException as e:
        error = SccApiError.from_exception(e)
        module.fail_json(**error.to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to list access policies: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

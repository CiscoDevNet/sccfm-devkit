# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import SccApiError
from cisco_sccfm_core.services.policy import AccessGroupService

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: list_access_groups
short_description: List ASA access groups in SCC Firewall Manager
description:
  - List ASA access groups from your SCC Firewall Manager tenant.
  - Supports pagination via C(limit) and C(offset).
  - Supports Lucene query filtering via C(query).
options:
  query:
    description: >-
      Optional Lucene query string to filter results.
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
  - Cisco SCCFM Team
"""

EXAMPLES = r"""
# List all access groups
- name: List access groups
  cisco.sccfm.list_access_groups:
    profile: default
  register: result

- name: Display access groups
  ansible.builtin.debug:
    var: result.access_groups

# Using module_defaults (recommended)
- name: List access groups with shared auth
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: List access groups
      cisco.sccfm.list_access_groups:
        limit: 100
"""

RETURN = r"""
access_groups:
  description: List of access groups returned by the API.
  returned: success
  type: list
  elements: dict
  contains:
    uid:
      description: Unique identifier.
      type: str
    name:
      description: Access group name.
      type: str
    entity_uid:
      description: UID of the device or manager.
      type: str
count:
  description: Total number of matching access groups.
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

    config: Config = create_config(module)
    params = module.params

    try:
        service = AccessGroupService(config=config)
        result = service.list_access_groups(
            query=params.get("query"),
            limit=params["limit"],
            offset=params["offset"],
        )
        module.exit_json(
            changed=False,
            access_groups=[group.to_dict() for group in result.items],
            count=result.count,
            limit=result.limit,
            offset=result.offset,
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to list access groups: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

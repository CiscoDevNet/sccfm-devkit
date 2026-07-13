# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import SccApiError
from cisco_sccfm_core.services.object_management import (
    NetworkGroupListResponse,
    NetworkGroupService,
)

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: list_network_groups
short_description: List network groups in SCC Firewall Manager
description:
  - List network groups from your SCC Firewall Manager tenant.
  - Supports pagination via C(limit) and C(offset).
  - "Supports Lucene query filtering via C(query) (searchable fields: name, content)."
  - Only returns NETWORK_GROUP types.
options:
  query:
    description: >-
      Optional Lucene query string to filter results.
      Searchable fields include C(name) and C(content).
      Example: C(name:web*) to find groups whose name starts with "web".
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
# Example 1: List all network groups
- name: List all network groups
  cisco.sccfm.list_network_groups:
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: result

- name: Display network groups
  ansible.builtin.debug:
    var: result.network_groups

# Example 2: Search with a query and pagination using module_defaults
- name: List network groups
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  tasks:
    - name: Find web-related network groups
      cisco.sccfm.list_network_groups:
        query: "name:web*"
        limit: 10
        offset: 0
      register: result

    - name: Show results
      ansible.builtin.debug:
        msg: "Found {{ result.count }} groups"

# Example 3: Using environment variables (SCCFM_REGION and SCCFM_API_TOKEN)
- name: List first page of network groups
  cisco.sccfm.list_network_groups:
    limit: 25
  register: result
"""

RETURN = r"""
network_groups:
  description:
    - List of network groups returned by the API.
    - Each item can include C(uid), C(name), C(description), C(elements),
      C(labels), C(tags), C(object_type), C(literals), and C(referenced_object_uids).
  returned: success
  type: list
  elements: dict
  contains:
    uid:
      description: Unique identifier of the network group.
      type: str
    name:
      description: Name of the network group.
      type: str
    labels:
      description: Labels attached to the group.
      type: list
    tags:
      description: Tags attached to the group.
      type: dict
    object_type:
      description: Type of the object.
      type: str
    literals:
      description: Literal values in the network group.
      type: list
    referenced_object_uids:
      description: UIDs of referenced objects in the group.
      type: list
count:
  description: Total number of matching network groups.
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


def list_network_groups(
    service: NetworkGroupService,
    *,
    query: str | None,
    limit: int,
    offset: int,
) -> NetworkGroupListResponse:
    """List network groups via the service layer."""
    return service.list_network_groups(
        limit=limit,
        offset=offset,
        query=query,
    )


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config: Config = create_config(module)

    params = module.params

    try:
        service = NetworkGroupService(config=config)
        result = list_network_groups(
            service,
            query=params.get("query"),
            limit=params["limit"],
            offset=params["offset"],
        )
        module.exit_json(
            changed=False,
            network_groups=[obj.to_dict() for obj in result.items],
            count=result.count,
            limit=result.limit,
            offset=result.offset,
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to list network groups: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from sccfm_core.errors import SccApiError
from sccfm_core.services.policy import AccessRuleService

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: list_access_rules
short_description: List ASA access rules in SCC Firewall Manager
description:
  - List ASA access rules from your SCC Firewall Manager tenant.
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
# Example 1: List all access rules
- name: List all access rules
  cisco.sccfm.list_access_rules:
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: result

- name: Display access rules
  ansible.builtin.debug:
    var: result.access_rules

# Example 2: Search with pagination using module_defaults
- name: List access rules
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  tasks:
    - name: List first page of access rules
      cisco.sccfm.list_access_rules:
        limit: 10
        offset: 0
      register: result

    - name: Show count
      ansible.builtin.debug:
        msg: "Found {{ result.count }} rules"
"""

RETURN = r"""
access_rules:
  description: List of access rules returned by the API.
  returned: success
  type: list
  elements: dict
  contains:
    uid:
      description: Unique identifier of the access rule.
      type: str
    rule_action:
      description: PERMIT or DENY.
      type: str
    index:
      description: Position in the rule list.
      type: int
    source_network:
      description: Source network details.
      type: dict
    destination_network:
      description: Destination network details.
      type: dict
count:
  description: Total number of matching access rules.
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

    if module.check_mode:
        module.exit_json(changed=False, access_rules=[], count=0, limit=0, offset=0)

    config: Config = create_config(module)
    params = module.params

    try:
        service = AccessRuleService(config=config)
        result = service.list_access_rules(
            query=params.get("query"),
            limit=params["limit"],
            offset=params["offset"],
        )
        module.exit_json(
            changed=False,
            access_rules=[rule.to_dict() for rule in result.items],
            count=result.count,
            limit=result.limit,
            offset=result.offset,
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to list access rules: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import SccApiError
from cisco_sccfm_core.services.policy import AccessRuleService

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: get_access_rule
short_description: Get an ASA access rule in SCC Firewall Manager
description:
  - Retrieve the full details of an ASA access rule by UID.
options:
  uid:
    description: Unique identifier (UID) of the access rule to retrieve.
    required: true
    type: str
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
# Example 1: Get access rule details by UID
- name: Get access rule
  cisco.sccfm.get_access_rule:
    uid: "ac981dcd-9860-401e-a51d-c615c946b72f"
    profile: default
  register: result

- name: Show rule
  ansible.builtin.debug:
    var: result.access_rule

# Example 2: Using module_defaults
- name: Inspect access rule
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Get access rule details
      cisco.sccfm.get_access_rule:
        uid: "{{ rule_uid }}"
      register: rule_result

    - name: Show rule action
      ansible.builtin.debug:
        msg: "Rule action: {{ rule_result.access_rule.rule_action }}"
"""

RETURN = r"""
access_rule:
  description: Full details of the access rule.
  returned: success
  type: dict
  contains:
    uid:
      description: Unique identifier of the access rule.
      type: str
    access_group_uid:
      description: UID of the associated access group.
      type: str
    entity_uid:
      description: UID of the device or manager.
      type: str
    index:
      description: Position in the rule list.
      type: int
    rule_action:
      description: PERMIT or DENY.
      type: str
    remark:
      description: Rule description.
      type: str
    source_network:
      description: Source network details.
      type: dict
    destination_network:
      description: Destination network details.
      type: dict
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "uid": {"type": "str", "required": True},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config: Config = create_config(module)
    uid: str = module.params["uid"]

    try:
        service = AccessRuleService(config=config)
        result = service.fetch_access_rule(uid=uid)
        module.exit_json(changed=False, access_rule=result.to_dict())
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to get access rule: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

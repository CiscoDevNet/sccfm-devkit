# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0
# flake8: noqa: E402
# isort: skip_file

from __future__ import annotations

DOCUMENTATION = r"""
---
module: create_access_rule
short_description: Create an ASA access rule in SCC Firewall Manager
description:
  - Create an ASA access rule in your SCC Firewall Manager tenant.
  - Supports specifying source and destination network objects by name.
  - Network object names are resolved to UIDs automatically.
  - Non-idempotent. This module creates a new access rule each time it runs.
options:
  access_group_uid:
    description: UID of the access group.
    required: true
    type: str
  entity_uid:
    description: UID of the device or manager.
    required: true
    type: str
  index:
    description: Position of the rule in the ordered list.
    required: true
    type: int
  rule_action:
    description: Rule action — PERMIT or DENY.
    required: false
    type: str
    default: PERMIT
    choices: [PERMIT, DENY]
  remark:
    description: Human-readable description of the rule.
    required: false
    type: str
  source_network:
    description: Source network object name.
    required: false
    type: str
  destination_network:
    description: Destination network object name.
    required: false
    type: str
  protocol:
    description: Protocol (e.g. tcp, udp, ip).
    required: false
    type: str
  source_port:
    description: Source port or port range.
    required: false
    type: str
  destination_port:
    description: Destination port or port range.
    required: false
    type: str
  log_level:
    description: Log level.
    required: false
    type: str
  log_interval:
    description: Log interval in seconds.
    required: false
    type: int
  active:
    description: Whether the rule is active.
    required: false
    type: bool
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
# Example 1: Create a permit rule with explicit credentials
- name: Create a permit rule for web traffic
  cisco.sccfm.create_access_rule:
    access_group_uid: "{{ access_group_uid }}"
    entity_uid: "{{ device_uid }}"
    index: 1
    rule_action: PERMIT
    source_network: web-servers
    destination_network: db-servers
    protocol: tcp
    destination_port: "443"
    remark: "Allow web to database"
    region: "{{ lookup('env', 'SCCFM_REGION') }}"
    api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"

# Example 2: Create a deny rule using module_defaults
- name: Create access rules
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ lookup('env', 'SCCFM_REGION') }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  tasks:
    - name: Create a deny rule for a source subnet
      cisco.sccfm.create_access_rule:
        access_group_uid: "{{ access_group_uid }}"
        entity_uid: "{{ device_uid }}"
        index: 10
        rule_action: DENY
        source_network: blocked-subnet
        destination_network: db-servers
        protocol: tcp
        destination_port: "1433"
        remark: "Block blocked-subnet to SQL"

# Example 3: Using environment variables (SCCFM_REGION and SCCFM_API_TOKEN)
- name: Create an inactive permit rule
  cisco.sccfm.create_access_rule:
    access_group_uid: "{{ access_group_uid }}"
    entity_uid: "{{ device_uid }}"
    index: 20
    source_network: web-servers
    destination_network: db-servers
    protocol: tcp
    destination_port: "443"
    active: false
    remark: "Prepared but not yet enabled"
"""

RETURN = r"""
access_rule:
  description: The created access rule.
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


from typing import Any

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.config import Config, base_argument_spec, create_config
from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException

    from cisco_sccfm_core.errors import SccApiError
    from cisco_sccfm_core.services.policy import AccessRuleService
except ImportError as exc:
    record_import_error(exc)


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "access_group_uid": {"type": "str", "required": True},
        "entity_uid": {"type": "str", "required": True},
        "index": {"type": "int", "required": True},
        "rule_action": {
            "type": "str",
            "required": False,
            "default": "PERMIT",
            "choices": ["PERMIT", "DENY"],
        },
        "remark": {"type": "str", "required": False},
        "source_network": {"type": "str", "required": False},
        "destination_network": {"type": "str", "required": False},
        "protocol": {"type": "str", "required": False},
        "source_port": {"type": "str", "required": False},
        "destination_port": {"type": "str", "required": False},
        "log_level": {"type": "str", "required": False},
        "log_interval": {"type": "int", "required": False},
        "active": {"type": "bool", "required": False},
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
        service = AccessRuleService(config=config)

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg="Would create access rule",
                access_rule={},
            )

        result = service.create_access_rule(
            access_group_uid=params["access_group_uid"],
            entity_uid=params["entity_uid"],
            index=params["index"],
            rule_action=params.get("rule_action") or "PERMIT",
            remark=params.get("remark"),
            source_network=params.get("source_network"),
            destination_network=params.get("destination_network"),
            protocol=params.get("protocol"),
            source_port=params.get("source_port"),
            destination_port=params.get("destination_port"),
            log_level=params.get("log_level"),
            log_interval=params.get("log_interval"),
            active=params.get("active"),
        )
        module.exit_json(
            changed=True,
            msg="Successfully created access rule",
            access_rule=result.to_dict(),
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to create access rule: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

DOCUMENTATION = r"""
---
module: update_access_rule
short_description: Update an ASA access rule in SCC Firewall Manager
description:
  - Update an ASA access rule in your SCC Firewall Manager tenant.
  - The rule is identified by C(uid).
  - At least one update field must be provided.
  - Non-idempotent. The update is always applied.
options:
  uid:
    description: Unique identifier (UID) of the access rule to update.
    required: true
    type: str
  index:
    description: New position of the rule in the ordered list.
    required: false
    type: int
  rule_action:
    description: Rule action — PERMIT or DENY.
    required: false
    type: str
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
# Example 1: Update a rule's action
- name: Change rule to DENY
  cisco.sccfm.update_access_rule:
    uid: "ac981dcd-9860-401e-a51d-c615c946b72f"
    rule_action: DENY
    profile: default

# Example 2: Update remark and networks using module_defaults
- name: Update access rules
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Update rule remark and source
      cisco.sccfm.update_access_rule:
        uid: "{{ rule_uid }}"
        remark: "Updated rule description"
        source_network: new-source-network
      register: result

    - name: Show updated rule
      ansible.builtin.debug:
        var: result.access_rule
"""

RETURN = r"""
access_rule:
  description: The updated access rule.
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

from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException

    from cisco_sccfm_core.errors import SccApiError
    from cisco_sccfm_core.services.policy import AccessRuleService
except ImportError as exc:
    record_import_error(exc)
    ApiException = RuntimeError
    NotFoundError = LookupError
    FtdConfigureManagerError = ValueError


from ..module_utils.config import Config, base_argument_spec, create_config

_UPDATE_FIELDS = [
    "index",
    "rule_action",
    "remark",
    "source_network",
    "destination_network",
    "protocol",
    "source_port",
    "destination_port",
    "log_level",
    "log_interval",
    "active",
]


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "uid": {"type": "str", "required": True},
        "index": {"type": "int", "required": False},
        "rule_action": {
            "type": "str",
            "required": False,
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

    update_kwargs: dict[str, Any] = {field: params.get(field) for field in _UPDATE_FIELDS}

    if not any(v is not None for v in update_kwargs.values()):
        module.fail_json(
            msg="At least one update field must be provided: " + ", ".join(_UPDATE_FIELDS)
        )

    if module.check_mode:
        module.exit_json(changed=True, msg="Would update access rule", access_rule={})
        return

    try:
        service = AccessRuleService(config=config)
        result = service.modify_access_rule(
            uid=params["uid"],
            **update_kwargs,
        )
        module.exit_json(
            changed=True,
            msg="Successfully updated access rule",
            access_rule=result.to_dict(),
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to update access rule: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

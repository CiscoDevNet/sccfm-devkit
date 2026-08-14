# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import NotFoundError, SccApiError
from cisco_sccfm_core.services.policy import AccessRuleService

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: delete_access_rule
short_description: Delete an ASA access rule in SCC Firewall Manager
description:
  - Delete an ASA access rule from your SCC Firewall Manager tenant.
  - The rule is identified by C(uid).
  - Idempotent. Returns C(changed=False) if the rule does not exist.
options:
  uid:
    description: Unique identifier (UID) of the access rule to delete.
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
# Example 1: Delete an access rule by UID
- name: Delete access rule
  cisco.sccfm.delete_access_rule:
    uid: "ac981dcd-9860-401e-a51d-c615c946b72f"
    profile: default

# Example 2: Delete using module_defaults
- name: Delete access rules
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Delete old rule
      cisco.sccfm.delete_access_rule:
        uid: "{{ rule_uid }}"
"""

RETURN = r"""
deleted_uid:
  description: The UID of the deleted access rule, or null if already absent.
  returned: always
  type: str
  sample: "ac981dcd-9860-401e-a51d-c615c946b72f"
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

    if module.check_mode:
        module.exit_json(
            changed=True,
            msg=f"Would delete access rule '{uid}'",
            deleted_uid=uid,
        )
        return

    try:
        service = AccessRuleService(config=config)
        deleted_uid = service.delete_access_rule(uid=uid)
        module.exit_json(
            changed=True,
            msg=f"Successfully deleted access rule '{deleted_uid}'",
            deleted_uid=deleted_uid,
        )
    except NotFoundError:
        module.exit_json(
            changed=False,
            msg=f"Access rule with UID '{uid}' not found; already absent.",
            deleted_uid=None,
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to delete access rule: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

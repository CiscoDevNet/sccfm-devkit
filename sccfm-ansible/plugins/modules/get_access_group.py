# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

DOCUMENTATION = r"""
---
module: get_access_group
short_description: Get an ASA access group in SCC Firewall Manager
description:
  - Retrieve the full details of an ASA access group by UID.
options:
  uid:
    description: Unique identifier (UID) of the access group to retrieve.
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
  - Cisco SCCFM Team (@CiscoDevNet)
"""

EXAMPLES = r"""
# Get access group details by UID
- name: Get access group
  cisco.sccfm.get_access_group:
    uid: "c6fa254e-db7a-447e-a58f-95df1e09c2af"
    profile: default
  register: result

- name: Show access group name
  ansible.builtin.debug:
    msg: "Access group: {{ result.access_group.name }}"

# Using module_defaults (recommended)
- name: Get access group with shared auth
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Get access group
      cisco.sccfm.get_access_group:
        uid: "c6fa254e-db7a-447e-a58f-95df1e09c2af"
"""

RETURN = r"""
access_group:
  description: Full details of the access group.
  returned: success
  type: dict
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
    is_shared:
      description: Whether the access group is shared.
      type: bool
"""


from typing import Any

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException

    from cisco_sccfm_core.errors import SccApiError
    from cisco_sccfm_core.services.policy import AccessGroupService
except ImportError as exc:
    record_import_error(exc)
    ApiException = RuntimeError
    NotFoundError = LookupError
    FtdConfigureManagerError = ValueError


from ..module_utils.config import Config, base_argument_spec, create_config


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
        service = AccessGroupService(config=config)
        result = service.fetch_access_group(uid=uid)
        module.exit_json(changed=False, access_group=result.to_dict())
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to get access group: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

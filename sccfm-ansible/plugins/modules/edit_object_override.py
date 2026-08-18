# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException

    from cisco_sccfm_core.errors import SccApiError
    from cisco_sccfm_core.services.object_management import ObjectOverrideService
except ImportError as exc:
    record_import_error(exc)
    ApiException = NotFoundError = FtdConfigureManagerError = RuntimeError


from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: edit_object_override
short_description: Edit an existing override value on an object in SCC Firewall Manager
description:
  - Edit the value of an existing device-specific override on an object.
  - The override must already exist for the given target device.
    Use M(cisco.sccfm.add_object_override) to create a new one.
  - All other overrides and the C(defaultContent) are preserved.
  - Supports C(NETWORK_OBJECT) and C(URL_OBJECT) types.
options:
  uid:
    description: Unique identifier (UID) of the object to edit.
    required: true
    type: str
  target_id:
    description: UID of the target device whose override value to edit.
    required: true
    type: str
  override_value:
    description: >-
      The new value for the override.
      For network objects this can be an IP address (e.g., C(10.0.0.1)),
      a CIDR subnet (e.g., C(10.0.0.0/24)), or an IP range.
      For URL objects this should be the URL string.
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
# Example 1: Edit an existing override for a specific device
- name: Update override value for branch office device
  cisco.sccfm.edit_object_override:
    uid: "abc-123-def"
    target_id: "70bde3c9-328c-4a4b-bdc9-a4d4042bf09a"
    override_value: "10.20.30.40"
    profile: default

# Example 2: Using module_defaults
- name: Edit object overrides
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Edit override
      cisco.sccfm.edit_object_override:
        uid: "{{ object_uid }}"
        target_id: "{{ device_uid }}"
        override_value: "{{ new_ip }}"
      register: edit_result

    - name: Show result
      ansible.builtin.debug:
        var: edit_result.object_override
"""

RETURN = r"""
object_override:
  description: The updated object state after the override was edited.
  returned: success
  type: dict
  contains:
    uid:
      description: Unique identifier of the object.
      type: str
    name:
      description: Name of the object.
      type: str
    object_type:
      description: Type of the object (e.g., NETWORK_OBJECT, URL_OBJECT).
      type: str
    overrides_count:
      description: Total number of overrides on the object.
      type: int
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "uid": {"type": "str", "required": True},
        "target_id": {"type": "str", "required": True},
        "override_value": {"type": "str", "required": True},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config: Config = create_config(module)

    params = module.params
    uid: str = params["uid"]
    target_id: str = params["target_id"]
    override_value: str = params["override_value"]

    if module.check_mode:
        module.exit_json(
            changed=True,
            msg=f"Would edit override for target '{target_id}' on object '{uid}'.",
            object_override={},
        )
        return

    try:
        service = ObjectOverrideService(config=config)
        result = service.edit_override(
            uid=uid,
            target_id=target_id,
            new_value=override_value,
        )
        module.exit_json(
            changed=True,
            msg=(
                f"Successfully updated override for target '{target_id}' "
                f"on object '{result.name}'."
            ),
            object_override=result.to_dict(),
        )
    except ValueError as e:
        module.fail_json(msg=str(e))
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to edit object override: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

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
module: delete_object_override
short_description: Delete an existing override from an object in SCC Firewall Manager
description:
  - Delete a device-specific override from an object.
  - The override must already exist for the given target device.
    Use M(cisco.sccfm.get_object) to list target IDs.
  - All other overrides and the C(defaultContent) are preserved.
  - Supports C(NETWORK_OBJECT) and C(URL_OBJECT) types.
options:
  uid:
    description: Unique identifier (UID) of the object.
    required: true
    type: str
  target_id:
    description: UID of the target device whose override to delete.
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
# Example 1: Delete an override for a specific device
- name: Remove override for branch office device
  cisco.sccfm.delete_object_override:
    uid: "abc-123-def"
    target_id: "70bde3c9-328c-4a4b-bdc9-a4d4042bf09a"
    profile: default

# Example 2: Using module_defaults
- name: Delete object overrides
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Delete override
      cisco.sccfm.delete_object_override:
        uid: "{{ object_uid }}"
        target_id: "{{ device_uid }}"
      register: delete_result

    - name: Show result
      ansible.builtin.debug:
        var: delete_result.object_override
"""

RETURN = r"""
object_override:
  description: The updated object state after the override was deleted.
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
      description: Total number of overrides remaining on the object.
      type: int
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "uid": {"type": "str", "required": True},
        "target_id": {"type": "str", "required": True},
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

    if module.check_mode:
        module.exit_json(
            changed=True,
            msg=f"Would delete override for target '{target_id}' on object '{uid}'.",
            object_override={},
        )
        return

    try:
        service = ObjectOverrideService(config=config)
        result = service.delete_override(
            uid=uid,
            target_id=target_id,
        )
        module.exit_json(
            changed=True,
            msg=(
                f"Successfully deleted override for target '{target_id}' "
                f"on object '{result.name}'."
            ),
            object_override=result.to_dict(),
        )
    except ValueError as e:
        module.fail_json(msg=str(e))
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to delete object override: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

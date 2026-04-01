from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule

from sccfm_core.services.object_management import ObjectOverrideService

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: update_object_default
short_description: Update the default content value of an object in SCC Firewall Manager
description:
  - Update the default content value of an object in your SCC Firewall Manager tenant.
  - The existing overrides are preserved — only C(defaultContent) is replaced.
  - Supports C(NETWORK_OBJECT) and C(URL_OBJECT) types.
options:
  uid:
    description: Unique identifier (UID) of the object to update.
    required: true
    type: str
  value:
    description: >-
      The new default value for the object.
      For network objects this can be an IP address (e.g., C(10.0.0.1)),
      a CIDR subnet (e.g., C(10.0.0.0/24)), or an IP range.
      For URL objects this should be the URL string.
    required: true
    type: str
  region:
    description: SCCFM region (int, us, eu, apj, aus, uae, in, or ci).
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
# Example 1: Update the default value of a network object
- name: Update default value for shared network object
  cisco.sccfm.update_object_default:
    uid: "abc-123-def"
    value: "10.10.10.10"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 2: Using module_defaults to avoid repeating credentials
- name: Update object default values
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  tasks:
    - name: Update default value
      cisco.sccfm.update_object_default:
        uid: "{{ object_uid }}"
        value: "{{ new_default_ip }}"
      register: update_result

    - name: Show result
      ansible.builtin.debug:
        var: update_result.object_default

# Example 3: Full override workflow — update default then add device override
- name: Configure object with default and device-specific override
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: Update shared default value
      cisco.sccfm.update_object_default:
        uid: "{{ object_uid }}"
        value: "192.168.1.1"

    - name: Add override for branch office device
      cisco.sccfm.add_object_override:
        uid: "{{ object_uid }}"
        target_id: "{{ branch_device_uid }}"
        override_value: "10.10.10.10"
"""

RETURN = r"""
object_default:
  description: The updated object state after the default value was changed.
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
    default_value:
      description: The new default content value.
      type: str
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "uid": {"type": "str", "required": True},
        "value": {"type": "str", "required": True},
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
    value: str = params["value"]

    if module.check_mode:
        module.exit_json(
            changed=True,
            msg=f"Would update default value of object '{uid}' to '{value}'.",
            object_default={},
        )
        return

    try:
        service = ObjectOverrideService(config=config)
        result = service.update_default_value(uid=uid, new_value=value)
        module.exit_json(
            changed=True,
            msg=f"Successfully updated default value of object '{result.name}' to '{result.default_value}'.",
            object_default=result.to_dict(),
        )
    except ValueError as e:
        module.fail_json(msg=str(e))
    except Exception as e:
        module.fail_json(msg=f"Failed to update object default value: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

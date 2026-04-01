from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule

from sccfm_core.services.object_management import ObjectOverrideService

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: get_object
short_description: Get the full details of an object in SCC Firewall Manager
description:
  - Retrieve the full details of an object by UID.
  - Returns the default value, all device-specific overrides, and the list of
    attached devices.
options:
  uid:
    description: Unique identifier (UID) of the object to retrieve.
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
# Example 1: Get object details by UID
- name: Get object
  cisco.sccfm.get_object:
    uid: "fd526e22-12ff-4fa0-a88d-7375c5d1e144"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: obj

- name: Show object
  ansible.builtin.debug:
    var: obj.object

# Example 2: Using module_defaults
- name: Inspect object before modifying overrides
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  tasks:
    - name: Get object details
      cisco.sccfm.get_object:
        uid: "{{ object_uid }}"
      register: obj_result

    - name: Show default value
      ansible.builtin.debug:
        msg: "Default value: {{ obj_result.object.default_value }}"
"""

RETURN = r"""
object:
  description: Full details of the object.
  returned: success
  type: dict
  contains:
    uid:
      description: Unique identifier of the object.
      type: str
    name:
      description: Name of the object.
      type: str
    description:
      description: Description of the object.
      type: str
    object_type:
      description: Type of the object (e.g., NETWORK_OBJECT, URL_OBJECT).
      type: str
    default_value:
      description: The default content value of the object.
      type: str
    overrides:
      description: List of device-specific overrides.
      type: list
      elements: dict
      contains:
        target_id:
          description: UID of the target device.
          type: str
        value:
          description: Override value for that device.
          type: str
    targets:
      description: List of devices the object is attached to.
      type: list
      elements: dict
      contains:
        id:
          description: UID of the device.
          type: str
        display_name:
          description: Display name of the device.
          type: str
        type:
          description: Device type.
          type: str
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
        module.exit_json(changed=False, object={})
        return

    try:
        service = ObjectOverrideService(config=config)
        result = service.get_object(uid=uid)
        module.exit_json(changed=False, object=result.to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to get object: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

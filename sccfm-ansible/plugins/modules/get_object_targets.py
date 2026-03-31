from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule

from sccfm_core.services.object_management import ObjectOverrideService

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: get_object_targets
short_description: Get the devices (targets) attached to an object in SCC Firewall Manager
description:
  - Retrieves the list of devices that a shared object is attached to.
  - Useful for discovering which devices can receive overrides for the object.
  - Supports any object type visible via the Object Management API.
options:
  uid:
    description: Unique identifier (UID) of the object.
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
# Example 1: Get all targets for an object
- name: Fetch targets for a network object
  cisco.sccfm.get_object_targets:
    uid: "abc-123-def"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: targets_result

- name: Show targets
  ansible.builtin.debug:
    var: targets_result.object_targets

# Example 2: Use the first target to add an override
- name: Get targets
  cisco.sccfm.get_object_targets:
    uid: "{{ object_uid }}"
  register: targets_result

- name: Add override on first target
  cisco.sccfm.add_object_override:
    uid: "{{ object_uid }}"
    target_id: "{{ targets_result.object_targets.targets[0].id }}"
    override_value: "10.10.10.10"
  when: targets_result.object_targets.targets | length > 0
"""

RETURN = r"""
object_targets:
  description: The object and its attached devices.
  returned: success
  type: dict
  contains:
    uid:
      description: Unique identifier of the object.
      type: str
    name:
      description: Name of the object.
      type: str
    targets:
      description: List of attached devices.
      type: list
      elements: dict
      contains:
        id:
          description: UID of the target device.
          type: str
        display_name:
          description: Display name of the target device.
          type: str
        type:
          description: Type of the target device.
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
        module.exit_json(
            changed=False,
            msg=f"Would fetch targets for object '{uid}'.",
            object_targets={},
        )
        return

    try:
        service = ObjectOverrideService(config=config)
        result = service.get_targets(uid=uid)
        module.exit_json(
            changed=False,
            msg=f"Found {len(result.targets)} target(s) for object '{result.name}'.",
            object_targets=result.to_dict(),
        )
    except Exception as e:
        module.fail_json(msg=f"Failed to get object targets: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

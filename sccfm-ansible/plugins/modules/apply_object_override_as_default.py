from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule

from sccfm_core.services.object_management import ObjectOverrideService

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: apply_object_override_as_default
short_description: Apply an override value as the new default on an object in SCC Firewall Manager
description:
  - Apply the override value of a specific target device as the new
    C(defaultContent) of the object.
  - The override for that target is removed from the list; all other overrides
    and the remaining overrides are preserved.
  - Supports C(NETWORK_OBJECT) and C(URL_OBJECT) types.
options:
  uid:
    description: Unique identifier (UID) of the object.
    required: true
    type: str
  target_id:
    description: UID of the target device whose override value to promote as the new default.
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
# Example 1: Promote a device override to become the new default
- name: Apply branch office override as new default
  cisco.sccfm.apply_object_override_as_default:
    uid: "abc-123-def"
    target_id: "897b293f-132e-4678-9d78-0f0947629500"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 2: Using module_defaults
- name: Apply object override as default
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  tasks:
    - name: Apply override as default
      cisco.sccfm.apply_object_override_as_default:
        uid: "{{ object_uid }}"
        target_id: "{{ device_uid }}"
      register: apply_result

    - name: Show result
      ansible.builtin.debug:
        var: apply_result.object_override
"""

RETURN = r"""
object_override:
  description: The updated object state after the override was applied as the new default.
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
            msg=f"Would apply override as default for target '{target_id}' to default on object '{uid}'.",
            object_override={},
        )
        return

    try:
        service = ObjectOverrideService(config=config)
        result = service.promote_override(
            uid=uid,
            target_id=target_id,
        )
        module.exit_json(
            changed=True,
            msg=f"Successfully applied override as default for target '{target_id}' to default on object '{result.name}'.",
            object_override=result.to_dict(),
        )
    except ValueError as e:
        module.fail_json(msg=str(e))
    except Exception as e:
        module.fail_json(msg=f"Failed to apply object override as default: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

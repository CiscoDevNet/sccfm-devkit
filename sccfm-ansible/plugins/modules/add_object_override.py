# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0
# flake8: noqa: E402
# isort: skip_file

from __future__ import annotations

DOCUMENTATION = r"""
---
module: add_object_override
short_description: Add a device-specific override to an object in SCC Firewall Manager
description:
  - Add a device-specific value override to an object in your SCC Firewall Manager tenant.
  - Overrides allow a shared object to have a different value on a specific managed device.
  - The object must already be attached to at least one device for overrides to apply.
  - Supports C(NETWORK_OBJECT) and C(URL_OBJECT) types.
  - The existing C(defaultContent) and any existing overrides are preserved.
options:
  uid:
    description: Unique identifier (UID) of the object to add the override to.
    required: true
    type: str
  target_id:
    description: UID of the target device for which the override applies.
    required: true
    type: str
  override_value:
    description: >-
      The literal value for the override.
      For network objects this can be an IP address (e.g., C(10.0.0.1)),
      a CIDR subnet (e.g., C(10.0.0.0/24)), or an IP range.
      For URL objects this should be the URL string.
    required: true
    type: str
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
# Example 1: Add an override for a specific device
- name: Add network object override for branch office device
  cisco.sccfm.add_object_override:
    uid: "abc-123-def"
    target_id: "70bde3c9-328c-4a4b-bdc9-a4d4042bf09a"
    override_value: "10.10.10.10"
    region: "{{ lookup('env', 'SCCFM_REGION') }}"
    api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"

# Example 2: Using module_defaults to avoid repeating credentials
- name: Add object overrides
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ lookup('env', 'SCCFM_REGION') }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  tasks:
    - name: Override web server IP for branch device
      cisco.sccfm.add_object_override:
        uid: "{{ object_uid }}"
        target_id: "{{ device_uid }}"
        override_value: "192.168.10.100"
      register: override_result

    - name: Show override result
      ansible.builtin.debug:
        var: override_result.object_override

# Example 3: Add overrides for multiple devices in a loop
- name: Add overrides for each branch office device
  cisco.sccfm.add_object_override:
    uid: "{{ shared_object_uid }}"
    target_id: "{{ item.device_uid }}"
    override_value: "{{ item.local_ip }}"
  loop: "{{ branch_offices }}"
  loop_control:
    label: "{{ item.name }}"
"""

RETURN = r"""
object_override:
  description: The updated object state after the override was added.
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
      description: Total number of overrides on the object after this operation.
      type: int
"""


from typing import Any

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.config import Config, base_argument_spec, create_config
from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException

    from cisco_sccfm_core.errors import SccApiError
    from cisco_sccfm_core.services.object_management import ObjectOverrideService
except ImportError as exc:
    record_import_error(exc)


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
            msg=f"Would add override for target '{target_id}' to object '{uid}'.",
            object_override={},
        )
        return

    try:
        service = ObjectOverrideService(config=config)
        result = service.add_override(
            uid=uid,
            target_id=target_id,
            override_value=override_value,
        )
        module.exit_json(
            changed=True,
            msg=f"Successfully added override for target '{target_id}' to object '{result.name}'.",
            object_override=result.to_dict(),
        )
    except ValueError as e:
        module.fail_json(msg=str(e))
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to add object override: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from sccfm_core.errors import NotFoundError, SccApiError
from sccfm_core.services.object_management import (
    NetworkGroupMemberMutationResult,
    NetworkGroupService,
)

from ..module_utils.config import (
    Config,
    base_argument_spec,
    create_config,
    identifier_argument_spec,
)

DOCUMENTATION = r"""
---
module: remove_network_group_members
short_description: Remove referenced members from a network group in SCC Firewall Manager
description:
  - Remove one or more referenced network objects from an existing network group.
  - The group can be identified by C(uid) or C(name) (exactly one required).
  - Only referenced network-object members are supported by this module.
  - Existing literals in the group are preserved unchanged.
  - The module is idempotent and returns C(changed=False) when all requested members
    are already absent.
options:
  uid:
    description: Unique identifier (UID) of the network group to update.
    required: false
    type: str
  name:
    description: Name of the network group to update.
    required: false
    type: str
  referenced_objects:
    description: >-
      List of existing network object names or UIDs to remove from the group.
      Names are resolved to UIDs automatically.
    required: true
    type: list
    elements: str
  region:
    description: SCCFM region (int, us, eu, apj, au, uae, in, or ci).
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
# Example 1: Remove members by name
- name: Remove members from a network group
  cisco.sccfm.remove_network_group_members:
    name: web-servers
    referenced_objects:
      - web-server-01
      - web-server-02
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 2: Remove members by UID
- name: Remove members from a network group by UID
  cisco.sccfm.remove_network_group_members:
    uid: "11111111-1111-1111-1111-111111111111"
    referenced_objects:
      - "22222222-2222-2222-2222-222222222222"
      - "33333333-3333-3333-3333-333333333333"

# Example 3: Using module_defaults (recommended)
- name: Remove network group members
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  tasks:
    - name: Remove old web servers from group
      cisco.sccfm.remove_network_group_members:
        name: web-servers
        referenced_objects:
          - old-web-server-01
          - old-web-server-02
"""

RETURN = r"""
network_group:
  description: The resulting network group state.
  returned: success
  type: dict
  contains:
    uid:
      description: Unique identifier of the network group.
      type: str
    name:
      description: Name of the network group.
      type: str
    description:
      description: Description of the network group.
      type: str
    elements:
      description: Elements associated with the group.
      type: list
    labels:
      description: Labels attached to the group.
      type: list
    tags:
      description: Tags attached to the group.
      type: dict
    object_type:
      description: Type of the object.
      type: str
    literals:
      description: Literal values in the group.
      type: list
    referenced_object_uids:
      description: UIDs of referenced objects in the group.
      type: list
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        **identifier_argument_spec(),
        "referenced_objects": {
            "type": "list",
            "elements": "str",
            "required": True,
        },
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        required_one_of=[["uid", "name"]],
        mutually_exclusive=[["uid", "name"]],
        supports_check_mode=True,
    )

    config: Config = create_config(module)

    uid: str | None = module.params.get("uid")
    name: str | None = module.params.get("name")
    referenced_objects: list[str] | None = module.params.get("referenced_objects")
    if not referenced_objects:
        module.fail_json(msg="At least one referenced_objects entry must be provided.")

    try:
        service = NetworkGroupService(config=config)
        result: NetworkGroupMemberMutationResult = service.remove_network_group_members(
            uid=uid,
            name=name,
            referenced_objects=referenced_objects,
            apply_changes=not module.check_mode,
        )

        if module.check_mode:
            if result.changed:
                module.exit_json(
                    changed=True,
                    msg=(
                        f"Network group '{result.network_group.name}' would have members removed."
                    ),
                    network_group=result.network_group.to_dict(),
                )
            module.exit_json(
                changed=False,
                msg=f"Network group '{result.network_group.name}' already excludes all requested members.",
                network_group=result.network_group.to_dict(),
            )
            return

        if result.changed:
            module.exit_json(
                changed=True,
                msg=f"Successfully removed members from network group '{result.network_group.name}'.",
                network_group=result.network_group.to_dict(),
            )
            return

        module.exit_json(
            changed=False,
            msg=f"Network group '{result.network_group.name}' already excludes all requested members.",
            network_group=result.network_group.to_dict(),
        )
    except NotFoundError as e:
        module.fail_json(msg=str(e))
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to remove network group members: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

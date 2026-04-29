from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from sccfm_core.errors import NotFoundError, SccApiError
from sccfm_core.services.object_management import NetworkGroupResponse, NetworkGroupService

from ..module_utils.config import (
    Config,
    base_argument_spec,
    create_config,
    identifier_argument_spec,
)
from ..module_utils.operations import fetch_object_by_identifier, fields_need_update

DOCUMENTATION = r"""
---
module: update_network_group
short_description: Update a network group in SCC Firewall Manager
description:
  - Update a network group in your SCC Firewall Manager tenant.
  - The group can be identified by C(uid) or C(name) (exactly one required).
  - Only fields that differ from the current state are sent, making the module idempotent.
  - Returns C(changed=False) when the group already matches the desired state.
  - Literal updates (network_literals, url_literals) are not supported for updates.
options:
  uid:
    description: Unique identifier (UID) of the network group to update.
    required: false
    type: str
  name:
    description: >-
      Name of the network group to update (alternative to C(uid)).
      Used to look up the group by name.
    required: false
    type: str
  new_name:
    description: New name for the network group (rename).
    required: false
    type: str
  referenced_objects:
    description: >-
      List of existing network object names or UIDs to include in the group.
      Names are resolved to UIDs automatically.
      Replaces all existing referenced objects.
    required: false
    type: list
    elements: str
  description:
    description: New description for the network group.
    required: false
    type: str
  labels:
    description: New list of labels for the network group.
    required: false
    type: list
    elements: str
  tags:
    description: >-
      New mapping of tag keys to lists of tag values.
      For example, C({"environment": ["production", "staging"]}).
    required: false
    type: dict
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
# Example 1: Update referenced objects by name
- name: Update network group members
  cisco.sccfm.update_network_group:
    name: web-servers
    referenced_objects:
      - web-server-01
      - web-server-02
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 2: Rename a group and update description using module_defaults
- name: Update network groups
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  tasks:
    - name: Rename and update group
      cisco.sccfm.update_network_group:
        name: web-servers
        new_name: web-tier
        description: "Updated web tier group"
        tags:
          environment:
            - production

# Example 3: Idempotent update (no change if already matching)
- name: Ensure group has correct description
  cisco.sccfm.update_network_group:
    name: app-tier
    description: "Application tier group"
  register: result

- name: Show whether a change was made
  ansible.builtin.debug:
    msg: "Changed: {{ result.changed }}"
"""

RETURN = r"""
network_group:
  description:
    - The updated network group, or current state if unchanged.
    - Returned keys include C(uid), C(name), C(description), C(elements),
      C(labels), C(tags), C(object_type), C(literals), and C(referenced_object_uids).
  returned: success
  type: dict
  contains:
    uid:
      description: Unique identifier of the network group.
      type: str
    name:
      description: Name of the network group.
      type: str
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
        "new_name": {"type": "str", "required": False, "default": None},
        "referenced_objects": {
            "type": "list",
            "elements": "str",
            "required": False,
            "default": None,
        },
        "description": {"type": "str", "required": False, "default": None},
        "labels": {"type": "list", "elements": "str", "required": False, "default": None},
        "tags": {"type": "dict", "required": False, "default": None},
        **base_argument_spec(),
    }


def _fetch_current_group(
    service: NetworkGroupService,
    *,
    uid: str | None,
    name: str | None,
) -> NetworkGroupResponse:
    """Fetch the current network group by UID or name."""
    return fetch_object_by_identifier(
        uid=uid,
        name=name,
        list_fn=lambda q, limit: service.list_network_groups(query=q, limit=limit),
        get_by_name_fn=service.get_network_group_by_name,
        entity_name="Network group",
    )


def _needs_update(
    current: NetworkGroupResponse,
    *,
    new_name: str | None,
    referenced_objects: list[str] | None,
    description: str | None,
    labels: list[str] | None,
    tags: dict[str, list[str]] | None,
) -> bool:
    """Compare desired state against current group to determine if an update is needed."""
    return fields_need_update(
        current={
            "name": current.name,
            "referenced_object_uids": current.referenced_object_uids,
            "description": current.description,
            "labels": current.labels,
            "tags": current.tags,
        },
        desired={
            "name": new_name,
            "referenced_object_uids": referenced_objects,
            "description": description,
            "labels": labels,
            "tags": tags,
        },
    )


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        required_one_of=[["uid", "name"]],
        mutually_exclusive=[["uid", "name"]],
        supports_check_mode=True,
    )

    config: Config = create_config(module)

    params = module.params
    uid: str | None = params.get("uid")
    name: str | None = params.get("name")
    new_name: str | None = params.get("new_name")
    referenced_objects: list[str] | None = params.get("referenced_objects")
    description: str | None = params.get("description")
    labels: list[str] | None = params.get("labels")
    tags: dict[str, list[str]] | None = params.get("tags")

    if not any([new_name, referenced_objects, description, labels, tags]):
        module.fail_json(
            msg="At least one update field must be provided: "
            "new_name, referenced_objects, description, labels, or tags."
        )

    try:
        service = NetworkGroupService(config=config)
        current = _fetch_current_group(service, uid=uid, name=name)

        if not _needs_update(
            current,
            new_name=new_name,
            referenced_objects=referenced_objects,
            description=description,
            labels=labels,
            tags=tags,
        ):
            module.exit_json(
                changed=False,
                msg=f"Network group '{current.name}' is already up to date.",
                network_group=current.to_dict(),
            )
            return

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Network group '{current.name}' would be updated.",
                network_group=current.to_dict(),
            )
            return

        result = service.update_network_group(
            uid=current.uid,
            new_name=new_name,
            referenced_objects=referenced_objects,
            description=description,
            labels=labels,
            tags=tags,
        )

        identifier = new_name or current.name
        module.exit_json(
            changed=True,
            msg=f"Successfully updated network group '{identifier}'.",
            network_group=result.to_dict(),
        )
    except NotFoundError as e:
        module.fail_json(msg=str(e))
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to update network group: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

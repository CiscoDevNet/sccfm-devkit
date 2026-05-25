# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from sccfm_core.errors import NotFoundError, SccApiError
from sccfm_core.services.object_management import NetworkObjectResponse, NetworkObjectService

from ..module_utils.config import (
    Config,
    base_argument_spec,
    create_config,
    identifier_argument_spec,
)
from ..module_utils.operations import fetch_object_by_identifier, fields_need_update

DOCUMENTATION = r"""
---
module: update_network_object
short_description: Update a network object in SCC Firewall Manager
description:
  - Update a network object in your SCC Firewall Manager tenant.
  - The object can be identified by C(uid) or C(name) (exactly one required).
  - Only fields that differ from the current state are sent, making the module idempotent.
  - Returns C(changed=False) when the object already matches the desired state.
options:
  uid:
    description: Unique identifier (UID) of the network object to update.
    required: false
    type: str
  name:
    description: >-
      Name of the network object to update (alternative to C(uid)).
      Used to look up the object by name.
    required: false
    type: str
  new_name:
    description: New name for the network object (rename).
    required: false
    type: str
  value:
    description: >-
      New literal value of the network object.
      Can be an IP address (e.g., C(10.0.0.1)),
      a CIDR subnet (e.g., C(10.0.0.0/24)),
      or an IP range (e.g., C(10.0.0.1-10.0.0.10)).
    required: false
    type: str
  description:
    description: New description for the network object.
    required: false
    type: str
  labels:
    description: New list of labels for the network object.
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
# Example 1: Update a network object's value by UID
- name: Update network object value
  cisco.sccfm.update_network_object:
    uid: "abc-123-def"
    value: "192.168.1.0/24"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 2: Rename a network object by name
- name: Rename a network object
  cisco.sccfm.update_network_object:
    name: old-object-name
    new_name: new-object-name
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 3: Update multiple fields using module_defaults
- name: Update network objects
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  tasks:
    - name: Update web server object
      cisco.sccfm.update_network_object:
        name: web-server-01
        value: "10.0.1.200"
        description: "Updated web server IP"
        labels:
          - production
          - web
        tags:
          environment:
            - production

# Example 4: Idempotent update (no change if already matching)
- name: Ensure network object has correct value
  cisco.sccfm.update_network_object:
    name: web-server-01
    value: "10.0.1.100"
  register: result

- name: Show whether a change was made
  ansible.builtin.debug:
    msg: "Changed: {{ result.changed }}"
"""

RETURN = r"""
network_object:
  description:
    - The updated network object, or current state if unchanged.
    - Returned keys include C(uid), C(name), C(description), C(elements),
      C(labels), C(tags), C(object_type), and C(literal).
  returned: success
  type: dict
  contains:
    uid:
      description: Unique identifier of the network object.
      type: str
    name:
      description: Name of the network object.
      type: str
    labels:
      description: Labels attached to the object.
      type: list
    tags:
      description: Tags attached to the object.
      type: dict
    object_type:
      description: Type of the object.
      type: str
    literal:
      description: Literal value of the network object.
      type: str
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        **identifier_argument_spec(),
        "new_name": {"type": "str", "required": False, "default": None},
        "value": {"type": "str", "required": False, "default": None},
        "description": {"type": "str", "required": False, "default": None},
        "labels": {"type": "list", "elements": "str", "required": False, "default": None},
        "tags": {"type": "dict", "required": False, "default": None},
        **base_argument_spec(),
    }


def _fetch_current_object(
    service: NetworkObjectService,
    *,
    uid: str | None,
    name: str | None,
) -> NetworkObjectResponse:
    """Fetch the current network object by UID or name."""
    return fetch_object_by_identifier(
        uid=uid,
        name=name,
        list_fn=lambda q, limit: service.list_network_objects(query=q, limit=limit),
        get_by_name_fn=service.get_network_object_by_name,
        entity_name="Network object",
    )


def _needs_update(
    current: NetworkObjectResponse,
    *,
    new_name: str | None,
    value: str | None,
    description: str | None,
    labels: list[str] | None,
    tags: dict[str, list[str]] | None,
) -> bool:
    """Compare desired state against current object to determine if an update is needed."""
    return fields_need_update(
        current={
            "name": current.name,
            "literal": current.literal,
            "description": current.description,
            "labels": current.labels,
            "tags": current.tags,
        },
        desired={
            "name": new_name,
            "literal": value,
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
    value: str | None = params.get("value")
    description: str | None = params.get("description")
    labels: list[str] | None = params.get("labels")
    tags: dict[str, list[str]] | None = params.get("tags")

    if not any([new_name, value, description, labels, tags]):
        module.fail_json(
            msg="At least one update field must be provided: "
            "new_name, value, description, labels, or tags."
        )

    try:
        service = NetworkObjectService(config=config)
        current = _fetch_current_object(service, uid=uid, name=name)

        if not _needs_update(
            current,
            new_name=new_name,
            value=value,
            description=description,
            labels=labels,
            tags=tags,
        ):
            module.exit_json(
                changed=False,
                msg=f"Network object '{current.name}' is already up to date.",
                network_object=current.to_dict(),
            )
            return

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Network object '{current.name}' would be updated.",
                network_object=current.to_dict(),
            )
            return

        result = service.update_network_object(
            uid=current.uid,
            new_name=new_name,
            value=value,
            description=description,
            labels=labels,
            tags=tags,
        )

        identifier = new_name or current.name
        module.exit_json(
            changed=True,
            msg=f"Successfully updated network object '{identifier}'.",
            network_object=result.to_dict(),
        )
    except NotFoundError as e:
        module.fail_json(msg=str(e))
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to update network object: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

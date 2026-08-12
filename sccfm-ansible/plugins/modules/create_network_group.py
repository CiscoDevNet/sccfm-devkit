# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0
# flake8: noqa: E402
# isort: skip_file

from __future__ import annotations

DOCUMENTATION = r"""
---
module: create_network_group
short_description: Create a network group in SCC Firewall Manager
description:
  - Create a network group in your SCC Firewall Manager tenant.
  - A group can contain network literals, URL literals, and/or referenced objects.
  - Network literals and URL literals are mutually exclusive.
  - Idempotent — if a network group with the same name already exists,
    the module returns C(ok) (changed=False) with the existing group.
options:
  name:
    description: Name of the network group.
    required: true
    type: str
  network_literals:
    description: >-
      List of network literal values (IP addresses, CIDR subnets, or IP ranges).
      Mutually exclusive with C(url_literals).
    required: false
    type: list
    elements: str
  url_literals:
    description: >-
      List of URL literal values.
      Mutually exclusive with C(network_literals).
    required: false
    type: list
    elements: str
  referenced_objects:
    description: >-
      List of existing network object names or UIDs to include in the group.
      Names are resolved to UIDs automatically.
    required: false
    type: list
    elements: str
  description:
    description: Optional description for the network group.
    required: false
    type: str
  labels:
    description: List of labels to attach to the network group.
    required: false
    type: list
    elements: str
  tags:
    description: >-
      Mapping of tag keys to lists of tag values.
      For example, C({"environment": ["production", "staging"]}).
    required: false
    type: dict
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
# Example 1: Create a group with network literals
- name: Create a network group with literals
  cisco.sccfm.create_network_group:
    name: web-servers
    network_literals:
      - "10.0.1.100"
      - "10.0.1.101"
    description: "Web server group"
    labels:
      - production
      - web
    region: "{{ lookup('env', 'SCCFM_REGION') }}"
    api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"

# Example 2: Create a group with referenced objects using module_defaults
- name: Create network groups
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ lookup('env', 'SCCFM_REGION') }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  tasks:
    - name: Create group from existing objects
      cisco.sccfm.create_network_group:
        name: app-tier
        referenced_objects:
          - web-server-01
          - app-server-01
        description: "Application tier group"
        tags:
          environment:
            - production

# Example 3: Using environment variables (SCCFM_REGION and SCCFM_API_TOKEN)
- name: Create a group with URL literals
  cisco.sccfm.create_network_group:
    name: trusted-urls
    url_literals:
      - "https://example.com"
      - "https://api.example.com"
    description: "Trusted URL group"
"""

RETURN = r"""
network_group:
  description:
    - The created network group.
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


from typing import Any

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.config import Config, base_argument_spec, create_config
from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException

    from cisco_sccfm_core.errors import SccApiError
    from cisco_sccfm_core.services.object_management import NetworkGroupService
except ImportError as exc:
    record_import_error(exc)


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "name": {"type": "str", "required": True},
        "network_literals": {"type": "list", "elements": "str", "required": False},
        "url_literals": {"type": "list", "elements": "str", "required": False},
        "referenced_objects": {"type": "list", "elements": "str", "required": False},
        "description": {"type": "str", "required": False},
        "labels": {"type": "list", "elements": "str", "required": False},
        "tags": {"type": "dict", "required": False},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        mutually_exclusive=[("network_literals", "url_literals")],
        supports_check_mode=True,
    )

    config: Config = create_config(module)

    params = module.params

    try:
        service = NetworkGroupService(config=config)
        existing = service.get_network_group_by_name(params["name"])
        if existing:
            module.exit_json(
                changed=False,
                msg=f"Network group '{params['name']}' already exists",
                network_group=existing.to_dict(),
            )

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Would create network group '{params['name']}'",
                network_group={},
            )

        result = service.create_network_group(
            name=params["name"],
            network_literals=params.get("network_literals"),
            url_literals=params.get("url_literals"),
            referenced_objects=params.get("referenced_objects"),
            description=params.get("description"),
            labels=params.get("labels"),
            tags=params.get("tags"),
        )
        module.exit_json(
            changed=True,
            msg=f"Successfully created network group '{params['name']}'",
            network_group=result.to_dict(),
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to create network group: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

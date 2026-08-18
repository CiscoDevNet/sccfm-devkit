# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import SccApiError
from cisco_sccfm_core.services.object_management import NetworkObjectService

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: create_network_object
short_description: Create a network object in SCC Firewall Manager
description:
  - Create a network object in your SCC Firewall Manager tenant.
  - Supports host IPs, CIDR subnets, and IP ranges as the object value.
  - Idempotent — if a network object with the same name already exists,
    the module returns C(ok) (changed=False) with the existing object.
options:
  name:
    description: Name of the network object.
    required: true
    type: str
  value:
    description: >-
      Literal value of the network object.
      Can be an IP address (e.g., C(10.0.0.1)),
      a CIDR subnet (e.g., C(10.0.0.0/24)),
      or an IP range (e.g., C(10.0.0.1-10.0.0.10)).
    required: true
    type: str
  description:
    description: Optional description for the network object.
    required: false
    type: str
  labels:
    description: List of labels to attach to the network object.
    required: false
    type: list
    elements: str
  tags:
    description: >-
      Mapping of tag keys to lists of tag values.
      For example, C({"environment": ["production", "staging"]}).
    required: false
    type: dict
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
# Example 1: Create a host network object
- name: Create a host network object
  cisco.sccfm.create_network_object:
    name: web-server-01
    value: "10.0.1.100"
    description: "Production web server"
    labels:
      - production
      - web
    profile: default

# Example 2: Create a subnet network object using module_defaults
- name: Create network objects
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Create branch office subnet
      cisco.sccfm.create_network_object:
        name: branch-office-subnet
        value: "10.10.0.0/24"
        description: "Branch office network"
        labels:
          - branch
          - subnet
        tags:
          environment:
            - production

# Example 3: Using the default configured profile
- name: Create a range network object
  cisco.sccfm.create_network_object:
    name: dhcp-pool
    value: "192.168.1.100-192.168.1.200"
    description: "DHCP address pool"
"""

RETURN = r"""
network_object:
  description:
    - The created network object, or the existing object if already present.
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
        "name": {"type": "str", "required": True},
        "value": {"type": "str", "required": True},
        "description": {"type": "str", "required": False},
        "labels": {"type": "list", "elements": "str", "required": False},
        "tags": {"type": "dict", "required": False},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config: Config = create_config(module)

    params = module.params
    name = params["name"]
    value = params["value"]

    try:
        service = NetworkObjectService(config=config)

        existing = service.get_network_object_by_name(name)

        if existing:
            module.exit_json(
                changed=False,
                msg=f"Network object '{name}' already exists",
                network_object=existing.to_dict(),
            )

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Would create network object '{name}'",
                network_object={},
            )

        result = service.create_network_object(
            name=name,
            value=value,
            description=params.get("description"),
            labels=params.get("labels"),
            tags=params.get("tags"),
        )
        module.exit_json(
            changed=True,
            msg=f"Successfully created network object '{name}'",
            network_object=result.to_dict(),
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to create network object: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

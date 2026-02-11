from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule

from sccfm_core.services.object_management import NetworkObjectResponse, NetworkObjectService
from sccfm_core.types import ConfigLike

from ..module_utils.config import Config

DOCUMENTATION = r"""
---
module: create_network_object
short_description: Create a network object in SCC Firewall Manager
description:
  - Create a network object in your SCC Firewall Manager tenant.
  - Supports host IPs, CIDR subnets, and IP ranges as the object value.
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
  region:
    description: SCCFM region (int, us, eu, apj, aus, uae, or in).
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
# Example 1: Create a host network object
- name: Create a host network object
  cisco.sccfm.create_network_object:
    name: web-server-01
    value: "10.0.1.100"
    description: "Production web server"
    labels:
      - production
      - web
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 2: Create a subnet network object using module_defaults
- name: Create network objects
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
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

# Example 3: Using environment variables (SCCFM_REGION and SCCFM_API_TOKEN)
- name: Create a range network object
  cisco.sccfm.create_network_object:
    name: dhcp-pool
    value: "192.168.1.100-192.168.1.200"
    description: "DHCP address pool"
"""

RETURN = r"""
network_object:
  description: The created network object.
  returned: success
  type: dict
  contains:
    uid:
      description: Unique identifier of the network object.
      type: str
    name:
      description: Name of the network object.
      type: str
    description:
      description: Description of the network object.
      type: str
    elements:
      description: Elements associated with the object.
      type: list
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
        "region": {"type": "str", "required": False},
        "api_token": {"type": "str", "required": False, "no_log": True},
    }


def create_network_object(
    config: ConfigLike,
    *,
    name: str,
    value: str,
    description: str | None,
    labels: list[str] | None,
    tags: dict[str, list[str]] | None,
) -> NetworkObjectResponse:
    """Create a network object via the service layer."""
    service = NetworkObjectService(config=config)
    return service.create_network_object(
        name=name,
        value=value,
        description=description,
        labels=labels,
        tags=tags,
    )


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=False,
    )

    try:
        config = Config(
            region=module.params.get("region") or "",
            api_token=module.params.get("api_token") or "",
        )
    except ValueError as e:
        module.fail_json(msg=str(e))

    params = module.params

    try:
        result = create_network_object(
            config,
            name=params["name"],
            value=params["value"],
            description=params.get("description"),
            labels=params.get("labels"),
            tags=params.get("tags"),
        )
        module.exit_json(
            changed=True,
            msg=f"Successfully created network object '{params['name']}'",
            network_object=result.to_dict(),
        )
    except Exception as e:
        module.fail_json(msg=f"Failed to create network object: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

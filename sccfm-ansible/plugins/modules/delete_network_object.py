# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule

from cisco_sccfm_core.services.object_management import NetworkObjectService

from ..module_utils.config import (
    Config,
    base_argument_spec,
    create_config,
    identifier_argument_spec,
)
from ..module_utils.operations import run_delete_with_idempotency

DOCUMENTATION = r"""
---
module: delete_network_object
short_description: Delete a network object in SCC Firewall Manager
description:
  - Delete a network object from your SCC Firewall Manager tenant.
  - Objects can be deleted by either UID or name.
options:
  uid:
    description: Unique identifier (UID) of the network object to delete.
    required: false
    type: str
  name:
    description: Name of the network object to delete.
    required: false
    type: str
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
notes:
  - Either C(uid) or C(name) must be provided, but not both.
  - When using C(name), the module will search for the object and resolve it to a UID before deletion.
author:
  - Cisco SCCFM Team
"""

EXAMPLES = r"""
# Example 1: Delete a network object by UID
- name: Delete network object by UID
  cisco.sccfm.delete_network_object:
    uid: "abc-123-def-456"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 2: Delete a network object by name
- name: Delete network object by name
  cisco.sccfm.delete_network_object:
    name: "old-web-server"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 3: Delete multiple objects using module_defaults
- name: Delete network objects
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  tasks:
    - name: Delete obsolete network objects
      cisco.sccfm.delete_network_object:
        name: "{{ item }}"
      loop:
        - old-server-01
        - old-server-02
        - deprecated-subnet

# Example 4: Using environment variables (SCCFM_REGION and SCCFM_API_TOKEN)
- name: Delete a network object
  cisco.sccfm.delete_network_object:
    name: "temporary-host"
"""

RETURN = r"""
deleted_uid:
  description: The UID of the deleted network object, or null if already absent.
  returned: always
  type: str
  sample: "abc-123-def-456"
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        **identifier_argument_spec(),
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
        required_one_of=[("uid", "name")],
        mutually_exclusive=[("uid", "name")],
    )

    config = create_config(module)
    service = NetworkObjectService(config=config)

    run_delete_with_idempotency(
        module,
        delete_fn=service.delete_network_object,
        uid=module.params.get("uid"),
        name=module.params.get("name"),
        entity_name="Network object",
        get_by_uid_fn=service.get_network_object,
        get_by_name_fn=service.get_network_object_by_name,
    )


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

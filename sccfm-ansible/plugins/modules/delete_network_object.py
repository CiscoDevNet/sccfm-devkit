from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule

from sccfm_core.errors import NotFoundError
from sccfm_core.services.object_management import NetworkObjectService
from sccfm_core.types import ConfigLike

from ..module_utils.config import Config

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
  description: The UID of the deleted network object.
  returned: success
  type: str
  sample: "abc-123-def-456"
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "uid": {"type": "str", "required": False},
        "name": {"type": "str", "required": False},
        "region": {"type": "str", "required": False},
        "api_token": {"type": "str", "required": False, "no_log": True},
    }


def delete_network_object(
    config: ConfigLike,
    *,
    uid: str | None,
    name: str | None,
) -> str:
    """Delete a network object via the service layer."""
    service = NetworkObjectService(config=config)
    return service.delete_network_object(uid=uid, name=name)


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=False,
        required_one_of=[("uid", "name")],
        mutually_exclusive=[("uid", "name")],
    )

    try:
        config = Config(
            region=module.params.get("region") or "",
            api_token=module.params.get("api_token") or "",
        )
    except ValueError as e:
        module.fail_json(msg=str(e))

    params = module.params
    identifier = params.get("uid") or params.get("name")
    identifier_type = "UID" if params.get("uid") else "name"

    try:
        deleted_uid = delete_network_object(
            config,
            uid=params.get("uid"),
            name=params.get("name"),
        )
        module.exit_json(
            changed=True,
            msg=f"Successfully deleted network object '{identifier}' ({identifier_type})",
            deleted_uid=deleted_uid,
        )
    except NotFoundError:
        module.exit_json(
            changed=False,
            msg=f"Network object '{identifier}' not found — already absent.",
        )
    except ValueError as e:
        module.fail_json(msg=f"Invalid parameters: {str(e)}")
    except Exception as e:
        module.fail_json(msg=f"Failed to delete network object: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

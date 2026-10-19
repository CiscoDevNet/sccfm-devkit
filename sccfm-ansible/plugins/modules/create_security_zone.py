# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import SccApiError
from cisco_sccfm_core.services.inventory.ftd_security_zone_service import (
    FtdSecurityZoneService,
)

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: create_security_zone
short_description: Create a security zone on a cdFMC domain
description:
  - Create a security zone object on cloud-delivered FMC.
  - Idempotent — if a zone with the same name already exists it is returned unchanged.
options:
  domain_uid:
    description: >-
      cdFMC domain UID. Obtain this from C(fmc_domain_uid) returned by C(list_managers).
    required: true
    type: str
  name:
    description: Name of the security zone.
    required: true
    type: str
  interface_mode:
    description: Interface mode for the zone.
    required: false
    type: str
    default: ROUTED
    choices: [ROUTED, INLINE, PASSIVE, TAP, ERSPAN]
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
- name: Create inside security zone
  cisco.sccfm.create_security_zone:
    domain_uid: "{{ cdfmc_domain_uid }}"
    name: "inside-zone"
    interface_mode: ROUTED
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: inside_zone_result

- name: Use the zone UID when configuring an interface
  cisco.sccfm.configure_ftd_interface:
    domain_uid: "{{ cdfmc_domain_uid }}"
    device_name: "vftd-a"
    interface_name: "GigabitEthernet0/1"
    nameif: "inside"
    ip_address: "11.11.11.10"
    netmask: "255.255.255.0"
    security_zone_uid: "{{ inside_zone_result.security_zone.id }}"
"""

RETURN = r"""
security_zone:
  description: The created or existing security zone.
  returned: success
  type: dict
  contains:
    id:
      description: Unique identifier of the security zone in cdFMC.
      type: str
    name:
      description: Name of the security zone.
      type: str
    interface_mode:
      description: Interface mode of the zone.
      type: str
changed:
  description: True if the zone was newly created, False if it already existed.
  returned: always
  type: bool
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "domain_uid": {"type": "str", "required": True},
        "name": {"type": "str", "required": True},
        "interface_mode": {
            "type": "str",
            "required": False,
            "default": "ROUTED",
            "choices": ["ROUTED", "INLINE", "PASSIVE", "TAP", "ERSPAN"],
        },
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config = create_config(module)
    domain_uid: str = module.params["domain_uid"]
    name: str = module.params["name"]
    interface_mode: str = module.params["interface_mode"]

    try:
        service = FtdSecurityZoneService(config=config)
        existing = next(
            (z for z in service.list_security_zones(domain_uid) if z.name == name),
            None,
        )

        if existing is not None:
            module.exit_json(
                changed=False,
                msg=f"Security zone '{name}' already exists",
                security_zone={"id": existing.id, "name": existing.name, "interface_mode": existing.interface_mode},
            )

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Would create security zone '{name}'",
                security_zone={},
            )

        zone = service.create_security_zone(domain_uid, name, interface_mode)  # type: ignore[arg-type]
        module.exit_json(
            changed=True,
            msg=f"Successfully created security zone '{name}'",
            security_zone={"id": zone.id, "name": zone.name, "interface_mode": zone.interface_mode},
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to create security zone: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

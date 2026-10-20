# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import SccApiError
from cisco_sccfm_core.services.inventory.ftd_physical_interface_service import (
    FtdPhysicalInterfaceService,
    Ipv4Config,
)

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: configure_ftd_interface
short_description: Configure a physical interface on a cdFMC-managed FTD
description:
  - Configure a physical interface (nameif, IP address, enabled state, security zone)
    on an FTD device managed by cloud-delivered FMC.
  - Requires the cdFMC domain UID (from C(list_managers)) and the FTD device name
    as it appears in cdFMC.
options:
  domain_uid:
    description: >-
      cdFMC domain UID. Obtain this from C(fmc_domain_uid) returned by C(list_managers).
    required: true
    type: str
  device_name:
    description: Name of the FTD device as registered in cdFMC.
    required: true
    type: str
  interface_name:
    description: Physical interface name (e.g. C(GigabitEthernet0/0)).
    required: true
    type: str
  nameif:
    description: Logical interface name (e.g. C(inside), C(outside)).
    required: true
    type: str
  ip_address:
    description: IPv4 address to assign to the interface.
    required: false
    type: str
  netmask:
    description: Subnet mask for the IPv4 address (e.g. C(255.255.255.0)).
    required: false
    type: str
  enabled:
    description: Whether the interface should be administratively enabled.
    required: false
    type: bool
    default: true
  security_zone_uid:
    description: UID of the security zone to assign to the interface.
    required: false
    type: str
  mode:
    description: >-
      Interface mode (e.g. C(NONE) for a standard routed interface,
      C(PASSIVE), C(INLINE), C(ERSPAN), C(TAP)). cdFMC requires this on
      every write; it is not reliably inherited from the interface's
      current configuration.
    required: false
    type: str
    default: NONE
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
- name: Configure inside interface on vFTD
  cisco.sccfm.configure_ftd_interface:
    domain_uid: "{{ cdfmc_domain_uid }}"
    device_name: "vftd-a"
    interface_name: "GigabitEthernet0/1"
    nameif: "inside"
    ip_address: "11.11.11.10"
    netmask: "255.255.255.0"
    enabled: true
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
"""

RETURN = r"""
interface:
  description: The updated physical interface configuration.
  returned: success
  type: dict
  contains:
    id:
      description: Unique identifier of the interface in cdFMC.
      type: str
    name:
      description: Physical interface name (e.g. GigabitEthernet0/0).
      type: str
    ifname:
      description: Logical interface name (nameif).
      type: str
    enabled:
      description: Whether the interface is administratively enabled.
      type: bool
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "domain_uid": {"type": "str", "required": True},
        "device_name": {"type": "str", "required": True},
        "interface_name": {"type": "str", "required": True},
        "nameif": {"type": "str", "required": True},
        "ip_address": {"type": "str", "required": False},
        "netmask": {"type": "str", "required": False},
        "enabled": {"type": "bool", "required": False, "default": True},
        "security_zone_uid": {"type": "str", "required": False},
        "mode": {"type": "str", "required": False, "default": "NONE"},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        required_together=[["ip_address", "netmask"]],
        supports_check_mode=True,
    )

    config = create_config(module)
    params = module.params

    domain_uid: str = params["domain_uid"]
    device_name: str = params["device_name"]
    interface_name: str = params["interface_name"]
    nameif: str = params["nameif"]
    ip_address: str | None = params.get("ip_address")
    netmask: str | None = params.get("netmask")
    enabled: bool = params["enabled"]
    security_zone_uid: str | None = params.get("security_zone_uid")
    mode: str = params["mode"]

    if module.check_mode:
        module.exit_json(
            changed=True,
            msg=f"Would configure interface '{interface_name}' on '{device_name}'",
            interface={},
        )

    try:
        service = FtdPhysicalInterfaceService(config=config)
        device_id = service.get_fmc_device_id(domain_uid, device_name)

        ipv4 = Ipv4Config(address=ip_address, netmask=netmask) if ip_address else None

        result = service.configure_interface(
            domain_uid,
            device_id,
            interface_name,
            nameif=nameif,
            ipv4=ipv4,
            enabled=enabled,
            security_zone_uid=security_zone_uid,
            mode=mode,
        )
        module.exit_json(
            changed=True,
            msg=f"Successfully configured interface '{interface_name}' on '{device_name}'",
            interface={"id": result.id, "name": result.name, "ifname": result.ifname, "enabled": result.enabled},
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to configure interface: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

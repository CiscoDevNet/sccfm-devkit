# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import SccApiError
from cisco_sccfm_core.services.inventory.ftd_virtual_tunnel_interface_service import (
    FtdVirtualTunnelInterfaceService,
    Ipv4Config,
)

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: create_vti_interface
short_description: Create a Virtual Tunnel Interface (VTI) on a cdFMC-managed FTD
description:
  - Create a route-based VPN virtual tunnel interface (VTI) on an FTD device managed by
    cloud-delivered FMC.
  - Idempotent by C(tunnel_id) - if a VTI with the same tunnel_id already exists on the
    device, it is returned unchanged rather than creating a duplicate.
  - Requires the cdFMC domain UID (from C(list_managers)) and the FTD device name as it
    appears in cdFMC. The physical interface referenced by C(tunnel_source_interface_id)
    must already exist and be configured on the device (e.g. via C(configure_ftd_interface))
    before creating a VTI on top of it.
  - "WARNING: this module is built from the FMC API Explorer's documented request/response
    schemas for the virtualtunnelinterfaces resource. It has not yet been exercised against
    a live cdFMC tenant by this collection - verify behavior against your tenant (field
    names, defaults, and the handling of DYNAMIC/borrowed-IP tunnels) before relying on it
    in production automation."
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
  tunnel_id:
    description: Numeric tunnel ID for the VTI (e.g. C(5) produces a VTI named C(Tunnel5)).
    required: true
    type: int
  tunnel_source_interface_id:
    description: UID of the existing physical interface to use as the tunnel source.
    required: true
    type: str
  tunnel_source_interface_name:
    description: >-
      Name of the existing physical interface to use as the tunnel source
      (e.g. C(GigabitEthernet0/0)).
    required: true
    type: str
  ifname:
    description: Logical interface name for the VTI (e.g. C(tunnel-5)).
    required: true
    type: str
  tunnel_type:
    description: >-
      C(STATIC) assigns a fixed address via C(ip_address)/C(netmask).
      C(DYNAMIC) is not yet supported by this module (no borrowed-IP support).
    required: false
    type: str
    default: STATIC
    choices: [STATIC, DYNAMIC]
  ipsec_mode:
    description: Address family carried over the tunnel.
    required: false
    type: str
    default: ipv4
    choices: [ipv4, ipv6]
  ip_address:
    description: >-
      Static IPv4 address for the VTI. Required when C(tunnel_type=STATIC) and
      C(ipsec_mode=ipv4). IPv6 addressing is not yet supported by this module.
    required: false
    type: str
  netmask:
    description: Subnet mask for C(ip_address) (e.g. C(255.255.255.252)).
    required: false
    type: str
  enabled:
    description: Whether the VTI should be administratively enabled.
    required: false
    type: bool
    default: true
  security_zone_uid:
    description: UID of the security zone to assign to the VTI.
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
author:
  - Cisco SCCFM Team
"""

EXAMPLES = r"""
- name: Create a static IPv4 VTI for a route-based S2S tunnel
  cisco.sccfm.create_vti_interface:
    domain_uid: "{{ cdfmc_domain_uid }}"
    device_name: "vftd-a"
    tunnel_id: 5
    tunnel_source_interface_id: "{{ outside_interface_uid }}"
    tunnel_source_interface_name: "GigabitEthernet0/1"
    ifname: "tunnel-5"
    ip_address: "169.254.100.1"
    netmask: "255.255.255.252"
    security_zone_uid: "{{ vti_zone_result.security_zone.id }}"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
"""

RETURN = r"""
virtual_tunnel_interface:
  description: The created (or already-existing, if idempotent match found) VTI.
  returned: success
  type: dict
  contains:
    id:
      description: Unique identifier of the VTI in cdFMC.
      type: str
    name:
      description: Display name assigned by FMC (e.g. Tunnel5).
      type: str
    ifname:
      description: Logical interface name (nameif).
      type: str
    tunnel_id:
      description: Numeric tunnel ID.
      type: int
    enabled:
      description: Whether the VTI is administratively enabled.
      type: bool
changed:
  description: True if a new VTI was created, False if one with the same tunnel_id already existed.
  returned: always
  type: bool
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "domain_uid": {"type": "str", "required": True},
        "device_name": {"type": "str", "required": True},
        "tunnel_id": {"type": "int", "required": True},
        "tunnel_source_interface_id": {"type": "str", "required": True},
        "tunnel_source_interface_name": {"type": "str", "required": True},
        "ifname": {"type": "str", "required": True},
        "tunnel_type": {
            "type": "str",
            "required": False,
            "default": "STATIC",
            "choices": ["STATIC", "DYNAMIC"],
        },
        "ipsec_mode": {
            "type": "str",
            "required": False,
            "default": "ipv4",
            "choices": ["ipv4", "ipv6"],
        },
        "ip_address": {"type": "str", "required": False},
        "netmask": {"type": "str", "required": False},
        "enabled": {"type": "bool", "required": False, "default": True},
        "security_zone_uid": {"type": "str", "required": False},
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
    tunnel_id: int = params["tunnel_id"]
    ip_address: str | None = params.get("ip_address")
    netmask: str | None = params.get("netmask")

    if module.check_mode:
        module.exit_json(
            changed=True,
            msg=f"Would create VTI tunnel_id={tunnel_id} on '{device_name}'",
            virtual_tunnel_interface={},
        )

    try:
        service = FtdVirtualTunnelInterfaceService(config=config)
        device_id = service.get_fmc_device_id(domain_uid, device_name)

        ipv4 = Ipv4Config(address=ip_address, netmask=netmask) if ip_address else None

        changed, result = service.create_vti_interface(
            domain_uid,
            device_id,
            tunnel_id=tunnel_id,
            tunnel_source_interface_id=params["tunnel_source_interface_id"],
            tunnel_source_interface_name=params["tunnel_source_interface_name"],
            ifname=params["ifname"],
            tunnel_type=params["tunnel_type"],
            ipsec_mode=params["ipsec_mode"],
            ipv4=ipv4,
            enabled=params["enabled"],
            security_zone_uid=params.get("security_zone_uid"),
        )
        module.exit_json(
            changed=changed,
            msg=(
                f"Successfully created VTI '{result.ifname}' (tunnel_id={result.tunnel_id}) "
                f"on '{device_name}'"
                if changed
                else f"VTI with tunnel_id={tunnel_id} already exists on '{device_name}'"
            ),
            virtual_tunnel_interface={
                "id": result.id,
                "name": result.name,
                "ifname": result.ifname,
                "tunnel_id": result.tunnel_id,
                "enabled": result.enabled,
            },
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to create VTI interface: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

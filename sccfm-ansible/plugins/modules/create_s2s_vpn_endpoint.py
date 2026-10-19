# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import SccApiError
from cisco_sccfm_core.services.inventory.ftd_s2s_vpn_service import FtdS2SVpnService

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: create_s2s_vpn_endpoint
short_description: Add one side (endpoint) of an FTD site-to-site VPN topology on cdFMC
description:
  - Add a single endpoint to an existing route-based S2S VPN topology created by
    C(create_s2s_vpn_tunnel). Call this once per side of the tunnel - twice for an
    FTD-to-FTD topology, or once with C(device_name)/C(interface_uid) and once with
    C(peer_ip_address) for an FTD-to-extranet (third-party peer) topology.
  - Idempotent - an FTD-side endpoint is matched by device name, an extranet endpoint by
    peer IP address; a match is returned unchanged rather than creating a duplicate.
  - For the FTD side, C(interface_uid) must be the UID of an existing VTI on that device
    (e.g. from C(create_vti_interface)'s returned C(virtual_tunnel_interface.id)) - this
    mirrors how Cisco's own CDO backend (aegis/FmcVpnTunnelService.updateEndpoint) resolves
    a route-based tunnel's local interface.
options:
  endpoints_path:
    description: >-
      The relative endpoints path returned by C(create_s2s_vpn_tunnel) as
      C(tunnel.endpoints_path).
    required: true
    type: str
  device_id:
    description: >-
      cdFMC device record UID for the FTD side of this endpoint. Required (together with
      C(device_name) and C(interface_uid)) unless C(peer_ip_address) is set for an
      extranet endpoint.
    required: false
    type: str
  device_name:
    description: Name of the FTD device as registered in cdFMC, for the FTD side of this endpoint.
    required: false
    type: str
  interface_uid:
    description: UID of the existing VTI on C(device_name) to use as this endpoint's local interface.
    required: false
    type: str
  connection_type:
    description: Connection type for the FTD-side endpoint.
    required: false
    type: str
    default: BIDIRECTIONAL
    choices: [BIDIRECTIONAL, ORIGINATE_ONLY]
  peer_name:
    description: Display name for an extranet (non-FTD) peer endpoint. Defaults to C(peer_ip_address) if unset.
    required: false
    type: str
  peer_ip_address:
    description: >-
      Public/reachable IP address of a third-party (extranet) peer. Set this instead of
      C(device_name)/C(interface_uid) for the non-FTD side of a tunnel.
    required: false
    type: str
  is_dynamic_ip:
    description: Whether the extranet peer has a dynamic IP address.
    required: false
    type: bool
    default: false
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
- name: Add the FTD/VTI side of the tunnel
  cisco.sccfm.create_s2s_vpn_endpoint:
    endpoints_path: "{{ tunnel_result.tunnel.endpoints_path }}"
    device_id: "{{ ftd_device_id }}"
    device_name: "vftd-a"
    interface_uid: "{{ vti_result.virtual_tunnel_interface.id }}"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

- name: Add an extranet (third-party) peer side of the tunnel
  cisco.sccfm.create_s2s_vpn_endpoint:
    endpoints_path: "{{ tunnel_result.tunnel.endpoints_path }}"
    peer_ip_address: "203.0.113.50"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
"""

RETURN = r"""
endpoint:
  description: The created (or already-existing, if idempotent match found) endpoint.
  returned: success
  type: dict
  contains:
    id:
      description: Unique identifier of the endpoint in cdFMC.
      type: str
    name:
      description: Display name of the endpoint.
      type: str
changed:
  description: True if a new endpoint was created, False if a matching one already existed.
  returned: always
  type: bool
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "endpoints_path": {"type": "str", "required": True},
        "device_id": {"type": "str", "required": False},
        "device_name": {"type": "str", "required": False},
        "interface_uid": {"type": "str", "required": False},
        "connection_type": {
            "type": "str",
            "required": False,
            "default": "BIDIRECTIONAL",
            "choices": ["BIDIRECTIONAL", "ORIGINATE_ONLY"],
        },
        "peer_name": {"type": "str", "required": False},
        "peer_ip_address": {"type": "str", "required": False},
        "is_dynamic_ip": {"type": "bool", "required": False, "default": False},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        required_together=[["device_id", "device_name", "interface_uid"]],
        required_one_of=[["device_name", "peer_ip_address"]],
        mutually_exclusive=[["device_name", "peer_ip_address"]],
        supports_check_mode=True,
    )

    config = create_config(module)
    params = module.params
    endpoints_path: str = params["endpoints_path"]
    is_extranet = params.get("peer_ip_address") is not None

    if module.check_mode:
        module.exit_json(
            changed=True,
            msg="Would create S2S VPN endpoint",
            endpoint={},
        )

    try:
        service = FtdS2SVpnService(config=config)
        if is_extranet:
            peer_ip = params["peer_ip_address"]
            changed, endpoint = service.create_endpoint_extranet(
                endpoints_path,
                peer_name=params.get("peer_name") or peer_ip,
                peer_ip_address=peer_ip,
                is_dynamic_ip=params["is_dynamic_ip"],
            )
        else:
            changed, endpoint = service.create_endpoint_ftd(
                endpoints_path,
                device_id=params["device_id"],
                device_name=params["device_name"],
                interface_uid=params["interface_uid"],
                connection_type=params["connection_type"],
            )
        module.exit_json(
            changed=changed,
            msg=(
                f"Successfully created S2S VPN endpoint '{endpoint.name}'"
                if changed
                else f"S2S VPN endpoint '{endpoint.name}' already exists"
            ),
            endpoint={"id": endpoint.id, "name": endpoint.name},
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to create S2S VPN endpoint: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

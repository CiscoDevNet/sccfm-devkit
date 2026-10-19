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
module: create_s2s_vpn_tunnel
short_description: Create a route-based (VTI) FTD site-to-site VPN topology on cdFMC
description:
  - Create a point-to-point, route-based (VTI) site-to-site VPN topology, including its
    IKE and IPsec settings, on cloud-delivered FMC.
  - Idempotent by C(name) - if a topology with the same name already exists, it is
    returned unchanged (IKE/IPsec settings are not re-applied on a match).
  - This module only creates the tunnel topology object and its settings. It does not
    create endpoints - use C(create_s2s_vpn_endpoint) afterwards, once per side of the
    tunnel, passing this module's returned C(endpoints_path).
  - "Scope: this mirrors what Cisco's own CDO backend (aegis/FmcS2STunnelWriteRequestBuilder)
    actually implements for this resource - route-based/POINT_TO_POINT topologies with
    MANUAL_PRE_SHARED_KEY authentication only. Certificate-based authentication,
    HUB_AND_SPOKE/AUTO_VPN topologies, and policy-based (non-VTI) tunnels are not supported
    by this module."
options:
  domain_uid:
    description: >-
      cdFMC domain UID. Obtain this from C(fmc_domain_uid) returned by C(list_managers).
    required: true
    type: str
  name:
    description: Name of the VPN topology.
    required: true
    type: str
  ikev1_enabled:
    description: Whether IKEv1 is enabled on this topology.
    required: false
    type: bool
    default: false
  ikev1_psk:
    description: Manual pre-shared key for IKEv1. Required when C(ikev1_enabled=true).
    required: false
    type: str
    no_log: true
  ikev1_policy_uids:
    description: UIDs of IKEv1 policy objects to attach. Required when C(ikev1_enabled=true).
    required: false
    type: list
    elements: str
  ikev1_ipsec_proposal_uids:
    description: UIDs of IKEv1 IPsec proposal objects to attach. Required when C(ikev1_enabled=true).
    required: false
    type: list
    elements: str
  ikev2_enabled:
    description: Whether IKEv2 is enabled on this topology.
    required: false
    type: bool
    default: true
  ikev2_psk:
    description: Manual pre-shared key for IKEv2. Required when C(ikev2_enabled=true).
    required: false
    type: str
    no_log: true
  ikev2_policy_uids:
    description: UIDs of IKEv2 policy objects to attach. Required when C(ikev2_enabled=true).
    required: false
    type: list
    elements: str
  ikev2_ipsec_proposal_uids:
    description: UIDs of IKEv2 IPsec proposal objects to attach. Required when C(ikev2_enabled=true).
    required: false
    type: list
    elements: str
  pfs_enabled:
    description: Whether Perfect Forward Secrecy is enabled on the IPsec settings.
    required: false
    type: bool
    default: false
  pfs_modulus_group:
    description: Diffie-Hellman modulus group number for PFS. Required when C(pfs_enabled=true).
    required: false
    type: int
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
- name: Create the S2S VPN topology
  cisco.sccfm.create_s2s_vpn_tunnel:
    domain_uid: "{{ cdfmc_domain_uid }}"
    name: "vftd-a-to-vftd-b"
    ikev2_enabled: true
    ikev2_psk: "{{ vpn_psk }}"
    ikev2_policy_uids: ["{{ ikev2_policy_uid }}"]
    ikev2_ipsec_proposal_uids: ["{{ ikev2_ipsec_proposal_uid }}"]
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: tunnel_result

- name: Add both endpoints (see create_s2s_vpn_endpoint)
  cisco.sccfm.create_s2s_vpn_endpoint:
    endpoints_path: "{{ tunnel_result.tunnel.endpoints_path }}"
    device_id: "{{ item.device_id }}"
    device_name: "{{ item.device_name }}"
    interface_uid: "{{ item.vti_uid }}"
  loop: "{{ tunnel_sides }}"
"""

RETURN = r"""
tunnel:
  description: The created (or already-existing, if idempotent match found) VPN topology.
  returned: success
  type: dict
  contains:
    id:
      description: Unique identifier of the topology in cdFMC.
      type: str
    name:
      description: Name of the topology.
      type: str
    endpoints_path:
      description: >-
        Relative API path for this topology's endpoints sub-resource. Pass this to
        C(create_s2s_vpn_endpoint)'s C(endpoints_path) parameter.
      type: str
changed:
  description: True if a new topology was created, False if one with the same name already existed.
  returned: always
  type: bool
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "domain_uid": {"type": "str", "required": True},
        "name": {"type": "str", "required": True},
        "ikev1_enabled": {"type": "bool", "required": False, "default": False},
        "ikev1_psk": {"type": "str", "required": False, "no_log": True},
        "ikev1_policy_uids": {
            "type": "list",
            "elements": "str",
            "required": False,
        },
        "ikev1_ipsec_proposal_uids": {
            "type": "list",
            "elements": "str",
            "required": False,
        },
        "ikev2_enabled": {"type": "bool", "required": False, "default": True},
        "ikev2_psk": {"type": "str", "required": False, "no_log": True},
        "ikev2_policy_uids": {
            "type": "list",
            "elements": "str",
            "required": False,
        },
        "ikev2_ipsec_proposal_uids": {
            "type": "list",
            "elements": "str",
            "required": False,
        },
        "pfs_enabled": {"type": "bool", "required": False, "default": False},
        "pfs_modulus_group": {"type": "int", "required": False},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        required_if=[
            ("ikev1_enabled", True, ["ikev1_psk", "ikev1_policy_uids"]),
            ("ikev2_enabled", True, ["ikev2_psk", "ikev2_policy_uids"]),
            ("pfs_enabled", True, ["pfs_modulus_group"]),
        ],
        supports_check_mode=True,
    )

    config = create_config(module)
    params = module.params
    name: str = params["name"]

    if module.check_mode:
        module.exit_json(
            changed=True, msg=f"Would create S2S VPN tunnel '{name}'", tunnel={}
        )

    try:
        service = FtdS2SVpnService(config=config)
        changed, tunnel = service.create_tunnel(
            params["domain_uid"],
            name=name,
            ikev1_enabled=params["ikev1_enabled"],
            ikev1_psk=params.get("ikev1_psk"),
            ikev1_policy_uids=params.get("ikev1_policy_uids"),
            ikev1_ipsec_proposal_uids=params.get("ikev1_ipsec_proposal_uids"),
            ikev2_enabled=params["ikev2_enabled"],
            ikev2_psk=params.get("ikev2_psk"),
            ikev2_policy_uids=params.get("ikev2_policy_uids"),
            ikev2_ipsec_proposal_uids=params.get("ikev2_ipsec_proposal_uids"),
            pfs_enabled=params["pfs_enabled"],
            pfs_modulus_group=params.get("pfs_modulus_group"),
        )
        module.exit_json(
            changed=changed,
            msg=(
                f"Successfully created S2S VPN tunnel '{tunnel.name}'"
                if changed
                else f"S2S VPN tunnel '{name}' already exists"
            ),
            tunnel={
                "id": tunnel.id,
                "name": tunnel.name,
                "endpoints_path": tunnel.endpoints_path,
            },
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to create S2S VPN tunnel: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

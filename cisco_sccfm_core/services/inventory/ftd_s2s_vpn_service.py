# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from scc_firewall_manager_sdk import ApiClient

from cisco_sccfm_core import ApiClientFactory
from cisco_sccfm_core.types import ConfigLike

_DEVICE_RECORDS_PATH = (
    "/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/devices/devicerecords"
)
_S2S_VPNS_PATH = "/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/policy/ftds2svpns"

# NOTE: Field names and the overall creation sequence (POST bare topology ->
# PUT ikeSettings -> PUT ipsecSettings -> POST endpoints, all driven off
# links embedded in the POST response, no extra GET required) are confirmed
# against aegis's (Cisco's own CDO backend) real, working FmcS2STunnelWriteRequestBuilder
# and its test fixtures (FmcVpnTunnelResponse.json, FmcVpnTunnelAddResponse.json) -
# this is NOT inferred from docs alone, unlike create_vti_interface. Scope is
# deliberately limited to what that real implementation actually supports:
# route-based (routeBased=true), POINT_TO_POINT topology, and
# MANUAL_PRE_SHARED_KEY authentication only. Certificate-based auth,
# hub-and-spoke/auto-vpn topologies, and policy-based (non-VTI) tunnels are
# out of scope - aegis itself doesn't implement them through this resource either.


@dataclass
class FtdS2SVpnTunnel:
    id: str
    name: str
    endpoints_path: str
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass
class FtdS2SVpnEndpoint:
    id: str
    name: str
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


def _relative_path_from_self_link(self_link: str) -> str:
    """Rewrite an absolute FMC self link into a path this client can call.

    FMC returns self links as full URLs against its own host, e.g.
    "https://<fmc-host>/api/fmc_config/v1/domain/.../ikesettings/{id}".
    aegis's own code (FmcS2STunnelToVpnTunnelConverter.addSelfLink) truncates
    everything up to and including "/api/" and replays the remainder against
    its own client - this mirrors that technique, replaying the remainder
    against our own "/v1/cdfmc/api/" gateway prefix instead.
    """
    marker = "/api/"
    idx = self_link.find(marker)
    if idx == -1:
        raise ValueError(f"Could not parse FMC self link: {self_link}")
    return "/v1/cdfmc/api/" + self_link[idx + len(marker) :]


class FtdS2SVpnService:
    def __init__(self, config: ConfigLike) -> None:
        self._api_client: ApiClient = ApiClientFactory().build(config)

    def _call(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        params = self._api_client.param_serialize(
            method=method,
            resource_path=path,
            path_params=None,
            query_params=None,
            header_params={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            body=body,
            post_params=None,
            files=None,
            auth_settings=["bearerAuth"],
            collection_formats=None,
        )
        response = self._api_client.call_api(*params)
        response.read()  # type: ignore[no-untyped-call]
        return json.loads(response.data) if response.data else {}

    def get_fmc_device_id(self, domain_uid: str, device_name: str) -> str:
        path = _DEVICE_RECORDS_PATH.format(domain_uid=domain_uid)
        params = self._api_client.param_serialize(
            method="GET",
            resource_path=path,
            path_params=None,
            query_params={"filter": f"name:{device_name}", "limit": 1},
            header_params={"Accept": "application/json"},
            body=None,
            post_params=None,
            files=None,
            auth_settings=["bearerAuth"],
            collection_formats=None,
        )
        response = self._api_client.call_api(*params)
        response.read()  # type: ignore[no-untyped-call]
        data = json.loads(response.data)
        items = data.get("items", [])
        if not items:
            raise ValueError(
                f"Device '{device_name}' not found in cdFMC domain '{domain_uid}'"
            )
        return str(items[0]["id"])

    def list_tunnels(self, domain_uid: str) -> list[dict[str, Any]]:
        path = _S2S_VPNS_PATH.format(domain_uid=domain_uid)
        params = self._api_client.param_serialize(
            method="GET",
            resource_path=path,
            path_params=None,
            query_params={"expanded": "true", "limit": 1000},
            header_params={"Accept": "application/json"},
            body=None,
            post_params=None,
            files=None,
            auth_settings=["bearerAuth"],
            collection_formats=None,
        )
        response = self._api_client.call_api(*params)
        response.read()  # type: ignore[no-untyped-call]
        data = json.loads(response.data)
        return list(data.get("items", []))

    def create_tunnel(
        self,
        domain_uid: str,
        *,
        name: str,
        ikev1_enabled: bool = False,
        ikev1_psk: str | None = None,
        ikev1_policy_uids: list[str] | None = None,
        ikev1_ipsec_proposal_uids: list[str] | None = None,
        ikev2_enabled: bool = True,
        ikev2_psk: str | None = None,
        ikev2_policy_uids: list[str] | None = None,
        ikev2_ipsec_proposal_uids: list[str] | None = None,
        pfs_enabled: bool = False,
        pfs_modulus_group: int | None = None,
    ) -> tuple[bool, FtdS2SVpnTunnel]:
        """Create a route-based (VTI) S2S VPN topology, idempotently by name.

        Returns (changed, tunnel). tunnel.endpoints_path is the relative path
        to POST endpoints to via create_endpoint() below.
        """
        existing = next(
            (t for t in self.list_tunnels(domain_uid) if t.get("name") == name), None
        )
        if existing is not None:
            endpoints = existing.get("endpoints", {})
            endpoints_self = endpoints.get("links", {}).get("self")
            return False, FtdS2SVpnTunnel(
                id=existing["id"],
                name=existing["name"],
                endpoints_path=(
                    _relative_path_from_self_link(endpoints_self)
                    if endpoints_self
                    else ""
                ),
                raw=existing,
            )

        create_path = _S2S_VPNS_PATH.format(domain_uid=domain_uid)
        created = self._call(
            "POST",
            create_path,
            {
                "name": name,
                "ikeV1Enabled": ikev1_enabled,
                "ikeV2Enabled": ikev2_enabled,
                "routeBased": True,
                "topologyType": "POINT_TO_POINT",
            },
        )

        ike_settings_self = created.get("ikeSettings", {}).get("links", {}).get("self")
        ipsec_settings_self = (
            created.get("ipsecSettings", {}).get("links", {}).get("self")
        )
        endpoints_self = created.get("endpoints", {}).get("links", {}).get("self")

        if ike_settings_self and (ikev1_enabled or ikev2_enabled):
            ike_body: dict[str, Any] = {}
            if ikev1_enabled:
                ike_body["ikeV1Settings"] = {
                    "authenticationType": "MANUAL_PRE_SHARED_KEY",
                    "manualPreSharedKey": ikev1_psk,
                    "policies": [{"id": uid} for uid in (ikev1_policy_uids or [])],
                }
            if ikev2_enabled:
                ike_body["ikeV2Settings"] = {
                    "authenticationType": "MANUAL_PRE_SHARED_KEY",
                    "manualPreSharedKey": ikev2_psk,
                    "policies": [{"id": uid} for uid in (ikev2_policy_uids or [])],
                }
            self._call(
                "PUT", _relative_path_from_self_link(ike_settings_self), ike_body
            )

        if ipsec_settings_self:
            ipsec_body: dict[str, Any] = {
                "perfectForwardSecrecy": {
                    "enabled": pfs_enabled,
                    **(
                        {"modulusGroup": pfs_modulus_group}
                        if pfs_modulus_group is not None
                        else {}
                    ),
                },
            }
            if ikev1_enabled:
                ipsec_body["ikeV1IpsecProposal"] = [
                    {"id": uid} for uid in (ikev1_ipsec_proposal_uids or [])
                ]
            if ikev2_enabled:
                ipsec_body["ikeV2IpsecProposal"] = [
                    {"id": uid} for uid in (ikev2_ipsec_proposal_uids or [])
                ]
            self._call(
                "PUT", _relative_path_from_self_link(ipsec_settings_self), ipsec_body
            )

        if "id" not in created:
            raise RuntimeError(
                f"POST to {create_path} returned HTTP 2xx but the response "
                f"did not contain the created tunnel's 'id' - the write was "
                f"likely not applied. Response body: {created!r}"
            )
        return True, FtdS2SVpnTunnel(
            id=created["id"],
            name=created.get("name", name),
            endpoints_path=(
                _relative_path_from_self_link(endpoints_self)
                if endpoints_self
                else ""
            ),
            raw=created,
        )

    def list_endpoints(self, endpoints_path: str) -> list[dict[str, Any]]:
        params = self._api_client.param_serialize(
            method="GET",
            resource_path=endpoints_path,
            path_params=None,
            query_params={"expanded": "true", "limit": 1000},
            header_params={"Accept": "application/json"},
            body=None,
            post_params=None,
            files=None,
            auth_settings=["bearerAuth"],
            collection_formats=None,
        )
        response = self._api_client.call_api(*params)
        response.read()  # type: ignore[no-untyped-call]
        data = json.loads(response.data)
        return list(data.get("items", []))

    def create_endpoint_ftd(
        self,
        endpoints_path: str,
        *,
        domain_uid: str,
        device_name: str,
        interface_uid: str,
        connection_type: str = "BIDIRECTIONAL",
    ) -> tuple[bool, FtdS2SVpnEndpoint]:
        """Create (or find idempotently by device name) the FTD/VTI side of a tunnel endpoint.

        The device's cdFMC device-record id is resolved here from device_name via
        get_fmc_device_id() - it must NOT be accepted as a caller-supplied parameter.
        A caller-supplied id is easy to get wrong by passing a device id from a
        different namespace (e.g. CDO/SCCFM's own inventory device.uid, as returned
        by onboard_cdfmc_ftd/register_cdfmc_ftd) instead of the cdFMC domain-scoped
        devicerecords id this endpoint actually requires - both are syntactically
        valid UUIDs, so a mismatch isn't caught by validation and instead surfaces
        as an opaque backend "Internal Error" on this POST. Resolving by name here
        mirrors the pattern already used by configure_ftd_interface/create_vti_interface
        (FtdPhysicalInterfaceService/FtdVirtualTunnelInterfaceService's own
        get_fmc_device_id calls) rather than trusting a passed-in id.
        """
        device_id = self.get_fmc_device_id(domain_uid, device_name)
        existing = next(
            (
                e
                for e in self.list_endpoints(endpoints_path)
                if not e.get("extranet", False)
                and e.get("device", {}).get("name") == device_name
            ),
            None,
        )
        if existing is not None:
            return False, FtdS2SVpnEndpoint(
                id=existing["id"], name=existing.get("name", device_name), raw=existing
            )

        body = {
            "connectionType": connection_type,
            "extranet": False,
            "peerType": "PEER",
            "device": {"id": device_id, "name": device_name},
            "interface": {"id": interface_uid},
        }
        created = self._call("POST", endpoints_path, body)
        if "id" not in created:
            # Re-check by listing (same idempotency match used above) before
            # concluding the write failed - but if it's genuinely not there,
            # raise with the actual response rather than masking it as success.
            match = next(
                (
                    e
                    for e in self.list_endpoints(endpoints_path)
                    if not e.get("extranet", False)
                    and e.get("device", {}).get("name") == device_name
                ),
                None,
            )
            if match is None:
                raise RuntimeError(
                    f"POST to {endpoints_path} returned HTTP 2xx but the "
                    f"response did not contain the created endpoint's 'id', "
                    f"and no matching endpoint for device '{device_name}' was "
                    f"found on re-list - the write was likely not applied. "
                    f"Response body: {created!r}"
                )
            created = match
        return True, FtdS2SVpnEndpoint(
            id=created["id"], name=created.get("name", device_name), raw=created
        )

    def create_endpoint_extranet(
        self,
        endpoints_path: str,
        *,
        peer_name: str,
        peer_ip_address: str,
        is_dynamic_ip: bool = False,
    ) -> tuple[bool, FtdS2SVpnEndpoint]:
        """Create (or find idempotently by peer IP) the extranet (non-FTD peer) side of a tunnel endpoint."""
        existing = next(
            (
                e
                for e in self.list_endpoints(endpoints_path)
                if e.get("extranet", False)
                and e.get("extranetInfo", {}).get("ipAddress") == peer_ip_address
            ),
            None,
        )
        if existing is not None:
            return False, FtdS2SVpnEndpoint(
                id=existing["id"], name=existing.get("name", peer_name), raw=existing
            )

        body = {
            "extranet": True,
            "peerType": "PEER",
            # EndPoint.name is reportedly ignored by FMC in favor of
            # extranetInfo.name, but both are set here to be safe - same
            # precaution aegis's own builder takes (see
            # FmcS2STunnelWriteRequestBuilder.buildEndpointExtranet).
            "name": peer_name,
            "extranetInfo": {
                "name": peer_name,
                "ipAddress": peer_ip_address,
                "isDynamicIP": is_dynamic_ip,
            },
        }
        created = self._call("POST", endpoints_path, body)
        if "id" not in created:
            # Same re-check-before-raising approach as create_endpoint_ftd() above.
            match = next(
                (
                    e
                    for e in self.list_endpoints(endpoints_path)
                    if e.get("extranet", False)
                    and e.get("extranetInfo", {}).get("ipAddress") == peer_ip_address
                ),
                None,
            )
            if match is None:
                raise RuntimeError(
                    f"POST to {endpoints_path} returned HTTP 2xx but the "
                    f"response did not contain the created endpoint's 'id', "
                    f"and no matching extranet endpoint for peer "
                    f"'{peer_ip_address}' was found on re-list - the write "
                    f"was likely not applied. Response body: {created!r}"
                )
            created = match
        return True, FtdS2SVpnEndpoint(
            id=created["id"], name=created.get("name", peer_name), raw=created
        )

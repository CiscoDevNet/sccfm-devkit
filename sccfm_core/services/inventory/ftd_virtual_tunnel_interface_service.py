# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from scc_firewall_manager_sdk import ApiClient

from sccfm_core.factories import ApiClientFactory
from sccfm_core.types import ConfigLike

_DEVICE_RECORDS_PATH = (
    "/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/devices/devicerecords"
)
_VIRTUAL_TUNNEL_INTERFACES_PATH = (
    "/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}"
    "/devices/devicerecords/{device_id}/virtualtunnelinterfaces"
)

# NOTE: Confirmed from the FMC API Explorer's documented request/response
# schemas for the "virtualtunnelinterfaces" resource (not yet exercised
# against a live cdFMC tenant by this collection). The GET/response shape
# additionally carries id/links/metadata/name, which are server-assigned and
# intentionally omitted from the POST body built below.


@dataclass
class FtdVirtualTunnelInterface:
    id: str
    name: str
    ifname: str
    tunnel_id: int
    enabled: bool
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass
class Ipv4Config:
    address: str
    netmask: str


class FtdVirtualTunnelInterfaceService:
    def __init__(self, config: ConfigLike) -> None:
        self._api_client: ApiClient = ApiClientFactory().build(config)

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

    def list_vti_interfaces(
        self, domain_uid: str, device_id: str
    ) -> list[FtdVirtualTunnelInterface]:
        path = _VIRTUAL_TUNNEL_INTERFACES_PATH.format(
            domain_uid=domain_uid, device_id=device_id
        )
        params = self._api_client.param_serialize(
            method="GET",
            resource_path=path,
            path_params=None,
            query_params={"expanded": "true", "limit": 100},
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
        return [
            FtdVirtualTunnelInterface(
                id=item["id"],
                name=item.get("name", ""),
                ifname=item.get("ifname", ""),
                tunnel_id=item.get("tunnelId", -1),
                enabled=item.get("enabled", False),
                raw=item,
            )
            for item in data.get("items", [])
        ]

    def create_vti_interface(
        self,
        domain_uid: str,
        device_id: str,
        *,
        tunnel_id: int,
        tunnel_source_interface_id: str,
        tunnel_source_interface_name: str,
        ifname: str,
        tunnel_type: str = "STATIC",
        ipsec_mode: str = "ipv4",
        ipv4: Ipv4Config | None = None,
        enabled: bool = True,
        security_zone_uid: str | None = None,
    ) -> tuple[bool, FtdVirtualTunnelInterface]:
        """Create a VTI, idempotently by tunnel_id.

        Returns (changed, interface). If a VTI with the same tunnel_id already
        exists on the device, it is returned unchanged (changed=False) instead
        of creating a duplicate - mirroring create_security_zone's idempotency,
        since this resource has no natural unique key enforced client-side.
        """
        existing = next(
            (
                vti
                for vti in self.list_vti_interfaces(domain_uid, device_id)
                if vti.tunnel_id == tunnel_id
            ),
            None,
        )
        if existing is not None:
            return False, existing

        body: dict[str, Any] = {
            "type": "VTIInterface",
            "ifname": ifname,
            "enabled": enabled,
            "tunnelId": tunnel_id,
            "tunnelType": tunnel_type,
            "ipsecMode": ipsec_mode,
            "tunnelSource": {
                "id": tunnel_source_interface_id,
                "name": tunnel_source_interface_name,
                "type": "PhysicalInterface",
            },
        }
        if ipv4 is not None:
            body["ipv4"] = {
                "static": {
                    "address": ipv4.address,
                    "netmask": ipv4.netmask,
                }
            }
        if security_zone_uid is not None:
            body["securityZone"] = {"id": security_zone_uid, "type": "SecurityZone"}

        path = _VIRTUAL_TUNNEL_INTERFACES_PATH.format(
            domain_uid=domain_uid, device_id=device_id
        )
        params = self._api_client.param_serialize(
            method="POST",
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
        created = json.loads(response.data)
        return True, FtdVirtualTunnelInterface(
            id=created["id"],
            name=created.get("name", ""),
            ifname=created.get("ifname", ""),
            tunnel_id=created.get("tunnelId", tunnel_id),
            enabled=created.get("enabled", enabled),
            raw=created,
        )

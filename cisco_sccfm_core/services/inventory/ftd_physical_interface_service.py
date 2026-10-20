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
_PHYSICAL_INTERFACES_PATH = (
    "/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}"
    "/devices/devicerecords/{device_id}/physicalinterfaces"
)
_PHYSICAL_INTERFACE_PATH = (
    "/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}"
    "/devices/devicerecords/{device_id}/physicalinterfaces/{interface_id}"
)


@dataclass
class FtdPhysicalInterface:
    id: str
    name: str
    ifname: str
    enabled: bool
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass
class Ipv4Config:
    address: str
    netmask: str


class FtdPhysicalInterfaceService:
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

    def list_interfaces(
        self, domain_uid: str, device_id: str
    ) -> list[FtdPhysicalInterface]:
        path = _PHYSICAL_INTERFACES_PATH.format(
            domain_uid=domain_uid, device_id=device_id
        )
        params = self._api_client.param_serialize(
            method="GET",
            resource_path=path,
            path_params=None,
            query_params={"limit": 100},
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
            FtdPhysicalInterface(
                id=item["id"],
                name=item["name"],
                ifname=item.get("ifname", ""),
                enabled=item.get("enabled", False),
                raw=item,
            )
            for item in data.get("items", [])
        ]

    def configure_interface(
        self,
        domain_uid: str,
        device_id: str,
        interface_name: str,
        *,
        nameif: str,
        ipv4: Ipv4Config | None = None,
        enabled: bool = True,
        security_zone_uid: str | None = None,
        mode: str = "ROUTED",
    ) -> FtdPhysicalInterface:
        interfaces = self.list_interfaces(domain_uid, device_id)
        match = next((i for i in interfaces if i.name == interface_name), None)
        if match is None:
            available = [i.name for i in interfaces]
            raise ValueError(
                f"Interface '{interface_name}' not found on device. "
                f"Available: {available}"
            )

        body: dict[str, Any] = {
            **match.raw,
            "ifname": nameif,
            "enabled": enabled,
            # cdFMC requires "mode" on every PUT - a never-configured
            # interface's GET representation (match.raw) doesn't carry one,
            # so it must be set explicitly rather than inherited. Mirrors the
            # ROUTED mode create_security_zone sets on the security zone side.
            "mode": mode,
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

        path = _PHYSICAL_INTERFACE_PATH.format(
            domain_uid=domain_uid, device_id=device_id, interface_id=match.id
        )
        params = self._api_client.param_serialize(
            method="PUT",
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
        updated: dict[str, Any] = json.loads(response.data) if response.data else {}
        if "id" not in updated:
            # A 2xx response without the resource's "id" means the write was
            # not actually applied by cdFMC (confirmed: devices stay off the
            # "pending changes" list and the FTD CLI shows the interface
            # unconfigured after this call returns). Surface the raw response
            # instead of silently treating this as success.
            raise RuntimeError(
                f"PUT to {path} returned HTTP {response.status} but the "
                f"response did not contain the updated interface's 'id' - "
                f"the write was likely not applied. Response body: {updated!r}"
            )
        return FtdPhysicalInterface(
            id=updated["id"],
            name=updated.get("name", match.name),
            ifname=updated.get("ifname", nameif),
            enabled=updated.get("enabled", enabled),
            raw=updated,
        )

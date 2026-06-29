# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from scc_firewall_manager_sdk import ApiClient

from sccfm_core.factories import ApiClientFactory
from sccfm_core.types import ConfigLike

_SECURITY_ZONES_PATH = (
    "/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/object/securityzones"
)

InterfaceMode = Literal["ROUTED", "INLINE", "PASSIVE", "TAP", "ERSPAN"]


@dataclass
class SecurityZone:
    id: str
    name: str
    interface_mode: str


class FtdSecurityZoneService:
    def __init__(self, config: ConfigLike) -> None:
        self._api_client: ApiClient = ApiClientFactory().build(config)

    def list_security_zones(self, domain_uid: str) -> list[SecurityZone]:
        path = _SECURITY_ZONES_PATH.format(domain_uid=domain_uid)
        params = self._api_client.param_serialize(
            method="GET",
            resource_path=path,
            path_params=None,
            query_params={"limit": 200},
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
            SecurityZone(
                id=item["id"],
                name=item["name"],
                interface_mode=item.get("interfaceMode", "ROUTED"),
            )
            for item in data.get("items", [])
        ]

    def create_security_zone(
        self,
        domain_uid: str,
        name: str,
        interface_mode: InterfaceMode = "ROUTED",
    ) -> SecurityZone:
        path = _SECURITY_ZONES_PATH.format(domain_uid=domain_uid)
        body = {"name": name, "type": "SecurityZone", "interfaceMode": interface_mode}
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
        return SecurityZone(
            id=created["id"],
            name=created["name"],
            interface_mode=created.get("interfaceMode", interface_mode),
        )

    def get_or_create_security_zone(
        self,
        domain_uid: str,
        name: str,
        interface_mode: InterfaceMode = "ROUTED",
    ) -> SecurityZone:
        existing = next(
            (z for z in self.list_security_zones(domain_uid) if z.name == name),
            None,
        )
        if existing is not None:
            return existing
        return self.create_security_zone(domain_uid, name, interface_mode)

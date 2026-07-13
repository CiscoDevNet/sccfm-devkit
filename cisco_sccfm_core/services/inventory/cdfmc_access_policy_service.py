# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from dataclasses import dataclass

from scc_firewall_manager_sdk import ApiClient

from cisco_sccfm_core.factories import ApiClientFactory
from cisco_sccfm_core.types import ConfigLike


@dataclass
class FmcAccessPolicy:
    uid: str
    name: str


@dataclass
class FmcAccessPolicyPage:
    items: list[FmcAccessPolicy]
    count: int
    limit: int
    offset: int


class CdfmcAccessPolicyService:
    def __init__(self, config: ConfigLike) -> None:
        self._api_client: ApiClient = ApiClientFactory().build(config)

    def get_access_policies(
        self,
        domain_uid: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> FmcAccessPolicyPage:
        resource_path = f"/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/policy/accesspolicies"
        params = self._api_client.param_serialize(
            method="GET",
            resource_path=resource_path,
            path_params=None,
            query_params={"limit": limit, "offset": offset},
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
        items = [
            FmcAccessPolicy(uid=item["id"], name=item["name"]) for item in data.get("items", [])
        ]
        paging = data.get("paging") or {}
        return FmcAccessPolicyPage(
            items=items,
            count=int(paging.get("count", data.get("count", len(items)))),
            limit=int(paging.get("limit", data.get("limit", limit))),
            offset=int(paging.get("offset", data.get("offset", offset))),
        )

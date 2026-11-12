# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from collections.abc import Callable
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
        read_response: Callable[[], object] = response.read
        read_response()
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

    def create_access_policy(
        self,
        domain_uid: str,
        name: str,
        payload: dict | None = None,
    ) -> FmcAccessPolicy:
        """Create a new access policy from a caller-supplied payload.

        ``name`` and ``type`` are always forced onto the payload (overriding
        anything the caller passed for those two keys) so the created
        policy's name follows the caller's own naming convention
        (e.g. tied to a device name) regardless of what the raw payload
        contains. FMC's minimum required fields for AccessPolicy are
        ``name``, ``type``, and ``defaultAction`` - the caller is
        responsible for providing ``defaultAction`` (and anything else)
        via ``payload``.
        """
        resource_path = f"/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/policy/accesspolicies"
        body = {**(payload or {}), "name": name, "type": "AccessPolicy"}
        params = self._api_client.param_serialize(
            method="POST",
            resource_path=resource_path,
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
        read_response: Callable[[], object] = response.read
        read_response()
        created = json.loads(response.data)
        return FmcAccessPolicy(uid=created["id"], name=created["name"])

    def get_or_create_access_policy(
        self,
        domain_uid: str,
        name: str,
        payload: dict | None = None,
    ) -> tuple[FmcAccessPolicy, bool]:
        """Idempotently ensure an access policy with ``name`` exists.

        Returns ``(policy, created)`` - ``created`` is False when a policy
        with this name already existed (in which case ``payload`` is never
        sent - the existing policy is returned as-is), True when this call
        just created it.
        """
        existing_page = self.get_access_policies(domain_uid, limit=200)
        existing = next((p for p in existing_page.items if p.name == name), None)
        if existing is not None:
            return existing, False
        return self.create_access_policy(domain_uid, name, payload), True

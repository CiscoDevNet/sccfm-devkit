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
class IntrusionPolicy:
    uid: str
    name: str


class CdfmcIntrusionPolicyService:
    """Read-only lookups for FMC intrusion policies (e.g. 'Maximum Detection').

    Intrusion policies are domain-scoped objects, like access policies - the
    same name (e.g. "Maximum Detection") exists in every cdFMC domain but
    under a different UID, so callers that need to reference one across
    multiple domains/tenants should resolve it by name here rather than
    hardcoding a UID copied from one domain's API response.
    """

    def __init__(self, config: ConfigLike) -> None:
        self._api_client: ApiClient = ApiClientFactory().build(config)

    def list_intrusion_policies(
        self, domain_uid: str, *, limit: int = 200
    ) -> list[IntrusionPolicy]:
        resource_path = f"/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/policy/intrusionpolicies"
        params = self._api_client.param_serialize(
            method="GET",
            resource_path=resource_path,
            path_params=None,
            query_params={"limit": limit},
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
        return [
            IntrusionPolicy(uid=item["id"], name=item["name"])
            for item in data.get("items", [])
        ]

    def get_intrusion_policy_uid_by_name(self, domain_uid: str, name: str) -> str:
        match = next(
            (p for p in self.list_intrusion_policies(domain_uid) if p.name == name),
            None,
        )
        if match is None:
            raise ValueError(f"Intrusion policy '{name}' not found in domain '{domain_uid}'.")
        return match.uid

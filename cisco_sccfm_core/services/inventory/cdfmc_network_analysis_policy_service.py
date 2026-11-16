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
class NetworkAnalysisPolicy:
    uid: str
    name: str


class CdfmcNetworkAnalysisPolicyService:
    """Read-only lookups for FMC Network Analysis Policies (e.g. 'Maximum Detection').

    Network Analysis Policy is its own resource type (GET
    /policy/networkanalysispolicies), distinct from Intrusion Policy even
    though FMC ships same-named default pairs of the two (e.g. "Maximum
    Detection" exists as both an IntrusionPolicy and a NetworkAnalysisPolicy,
    under different UIDs). Like intrusion policies/variable sets, these are
    domain-scoped - the same name exists in every cdFMC domain under a
    different UID per domain/tenant, so resolve by name here rather than
    hardcoding a UID copied from one domain's API response.
    """

    def __init__(self, config: ConfigLike) -> None:
        self._api_client: ApiClient = ApiClientFactory().build(config)

    def list_network_analysis_policies(
        self, domain_uid: str, *, limit: int = 200
    ) -> list[NetworkAnalysisPolicy]:
        resource_path = (
            f"/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/policy/networkanalysispolicies"
        )
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
            NetworkAnalysisPolicy(uid=item["id"], name=item["name"])
            for item in data.get("items", [])
        ]

    def get_network_analysis_policy_uid_by_name(self, domain_uid: str, name: str) -> str:
        match = next(
            (p for p in self.list_network_analysis_policies(domain_uid) if p.name == name),
            None,
        )
        if match is None:
            raise ValueError(
                f"Network Analysis Policy '{name}' not found in domain '{domain_uid}'."
            )
        return match.uid

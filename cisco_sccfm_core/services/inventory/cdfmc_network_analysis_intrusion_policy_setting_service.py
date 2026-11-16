# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from collections.abc import Callable

from scc_firewall_manager_sdk import ApiClient

from cisco_sccfm_core.factories import ApiClientFactory
from cisco_sccfm_core.types import ConfigLike


class CdfmcNetworkAnalysisAndIntrusionPolicySettingService:
    """Read/update the 'Network Analysis and Intrusion Policies' advanced settings
    of an FMC access control policy.

    This is a sub-resource auto-created alongside the access policy itself
    (one per policy, with its own id) - GET /accesspolicies/{policy_id}/
    networkanalysisandintrusionpolicysettings (list) to learn its id, then
    PUT the mutated object back to the singular .../{setting_id} path.

    This endpoint is NOT documented in cisco_sccfm_core's local copy of the
    cdFMC OpenAPI spec as of 2026-11 - it was reverse-engineered from a real
    PUT request captured via browser devtools while editing this panel in
    the FMC/CDO UI (confirmed working: the UI's own save used this exact
    path/payload shape). Unlike some other access-policy sub-resources, this
    one is NOT reachable via the classic FMC GWT-RPC UI call either in a way
    that's automatable - this REST path is the only viable integration
    point found.
    """

    _SETTINGS_PATH = (
        "/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/policy/accesspolicies/"
        "{policy_id}/networkanalysisandintrusionpolicysettings"
    )

    def __init__(self, config: ConfigLike) -> None:
        self._api_client: ApiClient = ApiClientFactory().build(config)

    def get_setting(self, domain_uid: str, policy_id: str) -> dict:
        """Return the single Network Analysis and Intrusion Policy setting object
        for this access policy, as a raw dict (preserves every field FMC returns,
        including ones this service doesn't otherwise model)."""
        resource_path = self._SETTINGS_PATH.format(domain_uid=domain_uid, policy_id=policy_id)
        params = self._api_client.param_serialize(
            method="GET",
            resource_path=resource_path,
            path_params=None,
            query_params=None,
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
        items = data.get("items", [])
        if not items:
            raise ValueError(
                "No Network Analysis and Intrusion Policy setting found for access "
                f"policy '{policy_id}' in domain '{domain_uid}'."
            )
        return items[0]

    def update_setting(
        self,
        domain_uid: str,
        policy_id: str,
        *,
        base_ips_policy: dict,
        base_ips_variable_set: dict,
        default_network_analysis_policy: dict,
    ) -> dict:
        """Update the three configurable references on this setting, leaving
        every other field (links, metadata, customNetworkAnalysisRules, ...)
        exactly as FMC last returned them - mirrors the real UI save captured
        via devtools, which sent the full GET-derived object back with only
        these fields changed (including a top-level 'links' key that, unlike
        some other cdFMC PUT endpoints, this one does NOT reject)."""
        existing = self.get_setting(domain_uid, policy_id)
        setting_id = existing["id"]

        body = dict(existing)
        body["baseInspection"] = {
            **(existing.get("baseInspection") or {}),
            "baseIpsPolicy": base_ips_policy,
            "baseIpsVariableSet": base_ips_variable_set,
        }
        body["networkAnalysis"] = {
            **(existing.get("networkAnalysis") or {}),
            "defaultNetworkAnalysisPolicy": default_network_analysis_policy,
        }

        resource_path = (
            self._SETTINGS_PATH.format(domain_uid=domain_uid, policy_id=policy_id)
            + f"/{setting_id}"
        )
        params = self._api_client.param_serialize(
            method="PUT",
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
        return json.loads(response.data)

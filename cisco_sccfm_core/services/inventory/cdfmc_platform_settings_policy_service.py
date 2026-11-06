# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from scc_firewall_manager_sdk import ApiClient

from cisco_sccfm_core.factories import ApiClientFactory
from cisco_sccfm_core.types import ConfigLike

# WARNING: this service (platform settings policy lookup + device assignment)
# has not yet been exercised against a live cdFMC tenant - it mirrors the
# documented FMC "Policy Assignments" REST contract (the same assignment
# model FMC uses for NAT, QoS, health, and platform settings policies), but
# has not been confirmed with a real request/response the way
# cdfmc_access_policy_service and ftd_physical_interface_service have been.
# Confirm the exact request/response shape via API Explorer against a live
# tenant before relying on this in production - see the "metadata"/"links"
# PUT-body lesson already learned the hard way in
# ftd_physical_interface_service.configure_interface.

_DEVICE_RECORDS_PATH = (
    "/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/devices/devicerecords"
)
_PLATFORM_SETTINGS_POLICIES_PATH = (
    "/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}"
    "/policy/ftdplatformsettingspolicies"
)
_POLICY_ASSIGNMENTS_PATH = (
    "/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/assignment/policyassignments"
)
_POLICY_ASSIGNMENT_PATH = (
    "/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}"
    "/assignment/policyassignments/{assignment_id}"
)

_PLATFORM_SETTINGS_POLICY_TYPE = "FTDPlatformSettings"


@dataclass
class FmcPlatformSettingsPolicy:
    uid: str
    name: str


@dataclass
class PolicyAssignmentResult:
    assignment_id: str
    policy_uid: str
    policy_name: str
    device_id: str
    target_ids: list[str] = field(default_factory=list)
    already_assigned: bool = False


class CdfmcPlatformSettingsPolicyService:
    def __init__(self, config: ConfigLike) -> None:
        self._api_client: ApiClient = ApiClientFactory().build(config)

    def list_platform_settings_policies(
        self,
        domain_uid: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FmcPlatformSettingsPolicy]:
        path = _PLATFORM_SETTINGS_POLICIES_PATH.format(domain_uid=domain_uid)
        params = self._api_client.param_serialize(
            method="GET",
            resource_path=path,
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
        return [
            FmcPlatformSettingsPolicy(uid=item["id"], name=item["name"])
            for item in data.get("items", [])
        ]

    def get_policy_uid_by_name(self, domain_uid: str, name: str) -> str:
        policies = self.list_platform_settings_policies(domain_uid, limit=200)
        match = next((p for p in policies if p.name == name), None)
        if match is None:
            available = [p.name for p in policies]
            raise ValueError(
                f"Platform settings policy '{name}' not found in cdFMC domain "
                f"'{domain_uid}'. Available: {available}"
            )
        return match.uid

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

    def _find_assignment_for_policy(
        self, domain_uid: str, policy_uid: str
    ) -> dict[str, Any] | None:
        path = _POLICY_ASSIGNMENTS_PATH.format(domain_uid=domain_uid)
        params = self._api_client.param_serialize(
            method="GET",
            resource_path=path,
            path_params=None,
            # Policy assignments aren't reliably filterable server-side by
            # policy id across FMC versions, so list and filter client-side -
            # same approach FtdSecurityZoneService uses for name lookups.
            query_params={"expanded": "true", "limit": 200},
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
        for item in data.get("items", []):
            policy_ref = item.get("policy") or {}
            if policy_ref.get("id") == policy_uid:
                return dict(item)
        return None

    def assign_policy_to_device(
        self,
        domain_uid: str,
        policy_uid: str,
        policy_name: str,
        device_id: str,
    ) -> PolicyAssignmentResult:
        existing = self._find_assignment_for_policy(domain_uid, policy_uid)

        if existing is None:
            body: dict[str, Any] = {
                "type": "PolicyAssignment",
                "policy": {"id": policy_uid, "type": _PLATFORM_SETTINGS_POLICY_TYPE},
                "targets": [{"id": device_id, "type": "Device"}],
            }
            path = _POLICY_ASSIGNMENTS_PATH.format(domain_uid=domain_uid)
            method = "POST"
        else:
            existing_targets = existing.get("targets") or []
            target_ids = {t.get("id") for t in existing_targets}
            if device_id in target_ids:
                return PolicyAssignmentResult(
                    assignment_id=str(existing["id"]),
                    policy_uid=policy_uid,
                    policy_name=policy_name,
                    device_id=device_id,
                    target_ids=sorted(str(i) for i in target_ids if i),
                    already_assigned=True,
                )
            # "metadata" and "links" are server-generated response envelope
            # fields - echoing them back verbatim on PUT causes cdFMC to
            # reject the request, the same failure mode already confirmed
            # live for physical interface PUTs. Strip them here too.
            writable_raw = {
                k: v for k, v in existing.items() if k not in ("metadata", "links")
            }
            body = {
                **writable_raw,
                "targets": [*existing_targets, {"id": device_id, "type": "Device"}],
            }
            path = _POLICY_ASSIGNMENT_PATH.format(
                domain_uid=domain_uid, assignment_id=existing["id"]
            )
            method = "PUT"

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
        updated: dict[str, Any] = json.loads(response.data) if response.data else {}
        if "id" not in updated:
            # Same "2xx without an id means the write wasn't actually
            # applied" guard used by ftd_physical_interface_service - don't
            # trust the HTTP status code alone.
            raise RuntimeError(
                f"{method} to {path} returned HTTP {response.status} but the "
                f"response did not contain the assignment's 'id' - the write "
                f"was likely not applied. Response body: {updated!r}"
            )
        target_ids = {t.get("id") for t in updated.get("targets", [])}
        target_ids.add(device_id)
        return PolicyAssignmentResult(
            assignment_id=str(updated["id"]),
            policy_uid=policy_uid,
            policy_name=policy_name,
            device_id=device_id,
            target_ids=sorted(str(i) for i in target_ids if i),
            already_assigned=False,
        )

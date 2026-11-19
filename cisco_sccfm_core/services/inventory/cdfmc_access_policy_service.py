# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass

from scc_firewall_manager_sdk import ApiClient

from cisco_sccfm_core.constants import (
    DEFAULT_POLLING_INTERVAL_SEC,
    DEFAULT_TRANSACTION_TIMEOUT_SEC,
)
from cisco_sccfm_core.factories import ApiClientFactory
from cisco_sccfm_core.types import ConfigLike

# cdFMC's own async job system (NOT the CDO-level TransactionService/CdoTransaction -
# this is the fmc_config-internal job queue, same family used by bulk CLI commands in
# FtdCommandLineService's job/taskstatuses polling). Clonepolicies uses this family too.
_CLONE_TERMINAL_STATUSES = frozenset({"SUCCESS", "FAILED", "COMPLETED"})
_CLONE_FAILURE_STATUSES = frozenset({"FAILED"})


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

    def clone_access_policy(
        self,
        domain_uid: str,
        source_policy_id: str,
        clone_name: str,
        *,
        polling_interval_sec: int = DEFAULT_POLLING_INTERVAL_SEC,
        timeout_sec: int = DEFAULT_TRANSACTION_TIMEOUT_SEC,
    ) -> FmcAccessPolicy:
        """Clone an existing access policy via cdFMC's clonepolicies operation.

        Unlike ``create_access_policy`` (a plain POST of a caller-built payload), this
        carries over the source policy's full configuration as cdFMC itself understands
        it - including sub-resources a bare POST /accesspolicies create does NOT
        populate, such as the "Network Analysis and Intrusion Policies" advanced
        settings (see CdfmcNetworkAnalysisAndIntrusionPolicySettingService's docstring
        for the saga on why that sub-resource can't reliably be set on a freshly-POSTed
        policy). This is the whole reason this method exists: clone from a known-good,
        already-correctly-configured source policy instead of trying to reconstruct
        its advanced settings field by field.

        This endpoint (POST .../policy/operational/clonepolicies) is NOT in the
        documented cdFMC OpenAPI spec - reverse-engineered from a real request captured
        via browser devtools while using FMC/CDO's own "Copy" action on an access
        policy. It is asynchronous: the POST only submits a background job and returns
        immediately (the cloned policy does not exist yet when this call returns) - the
        response shape is ``{"policies": [{"id": <source id echoed back>, "type":
        "AccessPolicy", "cloneName": ..., "metadata": {"task": {"id": <task id>}}}]}``.
        This method submits the clone, polls cdFMC's own job/taskstatuses endpoint
        (same family FtdCommandLineService polls for bulk CLI commands) until the job
        reaches a terminal status, then looks up the new policy by ``clone_name`` -
        the completed task body does not echo back the new policy's own id, so finding
        it by name afterward is the reliable way to get its uid.
        """
        task_id = self._submit_clone(domain_uid, source_policy_id, clone_name)
        self._poll_clone_task(
            domain_uid,
            task_id,
            polling_interval_sec=polling_interval_sec,
            timeout_sec=timeout_sec,
        )
        return self._find_access_policy_by_name(domain_uid, clone_name)

    def _submit_clone(self, domain_uid: str, source_policy_id: str, clone_name: str) -> str:
        resource_path = (
            f"/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/policy/operational/clonepolicies"
        )
        body = {
            "policies": [
                {"id": source_policy_id, "type": "AccessPolicy", "cloneName": clone_name}
            ]
        }
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
        data = json.loads(response.data)
        policies = data.get("policies") or []
        if not policies:
            raise ValueError(f"clonepolicies response had no 'policies' entry: {data}")
        task_id = policies[0].get("metadata", {}).get("task", {}).get("id")
        if not task_id:
            raise ValueError(f"No task ID in clonepolicies response: {data}")
        return str(task_id)

    def _poll_clone_task(
        self,
        domain_uid: str,
        task_id: str,
        *,
        polling_interval_sec: int,
        timeout_sec: int,
    ) -> dict:
        resource_path = (
            f"/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/job/taskstatuses/{task_id}"
        )
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
        start = time.time()
        while True:
            response = self._api_client.call_api(*params)
            read_response: Callable[[], object] = response.read
            read_response()
            body = json.loads(response.data)
            status = body.get("status", "")
            if status in _CLONE_TERMINAL_STATUSES:
                if status in _CLONE_FAILURE_STATUSES:
                    raise RuntimeError(
                        f"cdFMC clonepolicies task '{task_id}' failed with status "
                        f"'{status}': {body.get('message', body)}"
                    )
                return body
            elapsed = time.time() - start
            if elapsed >= timeout_sec:
                raise TimeoutError(
                    f"cdFMC clonepolicies task '{task_id}' did not complete within "
                    f"{timeout_sec}s (last status: '{status}')"
                )
            time.sleep(polling_interval_sec)

    def _find_access_policy_by_name(self, domain_uid: str, name: str) -> FmcAccessPolicy:
        page = self.get_access_policies(domain_uid, limit=200)
        match = next((p for p in page.items if p.name == name), None)
        if match is None:
            raise ValueError(
                f"clonepolicies task completed but no access policy named '{name}' "
                f"was found in domain '{domain_uid}'."
            )
        return match

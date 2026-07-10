# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import ssl
import time
import urllib.request
from typing import Any

from scc_firewall_manager_sdk import Device

from cisco_sccfm_core.constants import DEFAULT_TRANSACTION_TIMEOUT_SEC, FAST_POLLING_INTERVAL_SEC
from cisco_sccfm_core.factories import ApiClientFactory
from cisco_sccfm_core.models.ftd_cli_result import FtdBulkCliResult, FtdDeviceCliResponse
from cisco_sccfm_core.services.inventory.inventory_service import InventoryService
from cisco_sccfm_core.types import ConfigLike

_CDFMC_PROXY_PREFIX = "/v1/cdfmc/api/fmc_config/v1/domain"
_BULK_COMMANDS_SUFFIX = "devices/devicerecords/operational/bulkcommands"
_TASK_STATUS_SUFFIX = "job/taskstatuses"
_DOWNLOAD_SUFFIX = "operational/downloadreports"

_TERMINAL_STATUSES = frozenset({"SUCCESS", "FAILED", "COMPLETED"})


class FtdCommandLineService:
    """Execute CLI show commands on cdFMC-managed FTD devices.

    Uses the cdFMC bulk command proxy endpoint (no SDK wrapper available).
    """

    def __init__(self, config: ConfigLike) -> None:
        self._config = config
        api_client = ApiClientFactory().build(config=config)
        self._base_url: str = api_client.configuration.host
        self._token: str = api_client.configuration.access_token or config.api_token
        self._ssl_ctx = ssl.create_default_context()
        self._inventory_service = InventoryService(config=config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_cli(
        self,
        devices: list[Device],
        command: str,
        *,
        polling_interval_sec: int = FAST_POLLING_INTERVAL_SEC,
        timeout_sec: int = DEFAULT_TRANSACTION_TIMEOUT_SEC,
        on_poll: Any | None = None,
    ) -> FtdBulkCliResult:
        """Run a single ``show`` command on one or more FTD devices.

        Steps:
        1. Resolve cdFMC domain UUID.
        2. Map SCC device UIDs → FMC device-record UIDs.
        3. POST bulk command.
        4. Poll the async task until completion.
        5. Download and parse the report.
        """
        command = _validate_show_command(command)
        domain_uid = self._get_cdfmc_domain_uid()
        fmc_uid_map = _build_fmc_uid_map(devices)
        fmc_device_uids = list(fmc_uid_map.keys())
        if not fmc_device_uids:
            return FtdBulkCliResult(command=command, device_responses=[])

        task_id = self._submit_bulk_command(
            domain_uid=domain_uid,
            fmc_device_uids=fmc_device_uids,
            command=command,
        )
        task_body = self._poll_task(
            domain_uid=domain_uid,
            task_id=task_id,
            polling_interval_sec=polling_interval_sec,
            timeout_sec=timeout_sec,
            on_poll=on_poll,
        )
        download_url = _extract_download_url(task_body)
        return self._download_report(download_url=download_url)

    # ------------------------------------------------------------------
    # cdFMC domain resolution
    # ------------------------------------------------------------------

    def _get_cdfmc_domain_uid(self) -> str:
        """Retrieve the cdFMC domain UUID via the device-managers API."""
        page = self._inventory_service.get_managers(limit=1, offset=0, query="deviceType:CDFMC")
        managers = page.items or []
        if not managers:
            raise ValueError("No cdFMC manager found in this tenant.")
        domain_uid = managers[0].fmc_domain_uid
        if not domain_uid:
            raise ValueError("cdFMC manager has no domain UID.")
        return domain_uid

    # ------------------------------------------------------------------
    # HTTP helpers (raw urllib — no SDK wrapper for these endpoints)
    # ------------------------------------------------------------------

    def _submit_bulk_command(
        self,
        *,
        domain_uid: str,
        fmc_device_uids: list[str],
        command: str,
    ) -> str:
        url = f"{self._base_url}{_CDFMC_PROXY_PREFIX}/{domain_uid}/" f"{_BULK_COMMANDS_SUFFIX}"
        payload = json.dumps({"command": command, "devices": fmc_device_uids}).encode()
        body = self._http_request(url=url, method="POST", data=payload)
        task_id = body.get("metadata", {}).get("task", {}).get("id")
        if not task_id:
            raise ValueError(f"No task ID in bulk command response: {body}")
        return str(task_id)

    def _poll_task(
        self,
        *,
        domain_uid: str,
        task_id: str,
        polling_interval_sec: int,
        timeout_sec: int,
        on_poll: Any | None,
    ) -> dict[str, Any]:
        url = (
            f"{self._base_url}{_CDFMC_PROXY_PREFIX}/{domain_uid}/"
            f"{_TASK_STATUS_SUFFIX}/{task_id}"
        )
        start = time.time()
        while True:
            body = self._http_request(url=url)
            status = body.get("status", "")
            if on_poll:
                on_poll(status)
            if status in _TERMINAL_STATUSES:
                return body
            elapsed = time.time() - start
            if elapsed >= timeout_sec:
                raise TimeoutError(
                    f"cdFMC task {task_id} did not complete within {timeout_sec}s "
                    f"(last status: {status})"
                )
            time.sleep(polling_interval_sec)

    def _download_report(self, *, download_url: str) -> FtdBulkCliResult:
        body = self._http_request(url=download_url)
        return _parse_bulk_report(body)

    def _http_request(
        self,
        *,
        url: str,
        method: str = "GET",
        data: bytes | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=60) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode(errors="replace")
            detail = _extract_error_detail(error_body)
            raise RuntimeError(f"cdFMC API error (HTTP {exc.code}): {detail}") from exc
        return dict(json.loads(raw))


# ------------------------------------------------------------------
# Pure helpers
# ------------------------------------------------------------------


def _build_fmc_uid_map(devices: list[Device]) -> dict[str, str]:
    """Map FMC device-record UIDs → SCC device UIDs.

    Prefer ``device_record_on_fmc.uid`` when present, but fall back to
    ``cd_fmc_info.fmc_device_record_uid`` because different API responses
    expose the FMC record UID through different fields.
    """
    fmc_to_scc: dict[str, str] = {}
    for device in devices:
        fmc_uid = _get_fmc_device_record_uid(device)
        device_uid = getattr(device, "uid", None)
        if fmc_uid and device_uid:
            fmc_to_scc[fmc_uid] = str(device_uid)
    return fmc_to_scc


def _get_fmc_device_record_uid(device: Device) -> str | None:
    device_record = getattr(device, "device_record_on_fmc", None)
    if device_record and getattr(device_record, "uid", None):
        return str(device_record.uid)

    cdfmc_info = getattr(device, "cd_fmc_info", None)
    if cdfmc_info and getattr(cdfmc_info, "fmc_device_record_uid", None):
        return str(cdfmc_info.fmc_device_record_uid)

    return None


def _validate_show_command(command: str) -> str:
    normalized = command.strip()
    if not normalized:
        raise ValueError("A non-empty CLI command is required.")
    if "\n" in normalized or "\r" in normalized:
        raise ValueError("Exactly one CLI command is supported per request.")

    lowered = normalized.casefold()
    if lowered != "show" and not lowered.startswith("show "):
        raise ValueError("Only show commands are supported for cdFMC-managed FTD CLI execution.")

    return normalized


def _extract_download_url(task_body: dict[str, Any]) -> str:
    url = task_body.get("metadata", {}).get("downloadUrl", "")
    if not url:
        status = task_body.get("status", "UNKNOWN")
        message = task_body.get("message", "")
        raise ValueError(
            f"cdFMC task completed with status '{status}' but no download URL. "
            f"Message: {message}"
        )
    return str(url)


def _parse_bulk_report(body: dict[str, Any]) -> FtdBulkCliResult:
    command = body.get("command", "")
    responses: list[FtdDeviceCliResponse] = []
    for item in body.get("deviceResponse", []):
        responses.append(
            FtdDeviceCliResponse(
                device_uuid=item.get("deviceUUID", ""),
                device_name=item.get("deviceName", ""),
                response=item.get("response"),
                is_error=item.get("isError", False),
                error_msg=item.get("errorMsg"),
            )
        )
    return FtdBulkCliResult(command=command, device_responses=responses)


def _extract_error_detail(body: str) -> str:
    """Pull a human-readable message from a cdFMC JSON error response."""
    try:
        data = json.loads(body)
        messages = data.get("error", {}).get("messages", [])
        if messages:
            return str(messages[0].get("description", body))
    except (json.JSONDecodeError, AttributeError, IndexError):
        pass
    return body[:500] if body else "No details available"

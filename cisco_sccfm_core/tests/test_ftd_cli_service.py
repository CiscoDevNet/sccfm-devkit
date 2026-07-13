# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for FtdCommandLineService."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from scc_firewall_manager_sdk import Device, DevicePage, EntityType

from cisco_sccfm_core.models.ftd_cli_result import FtdBulkCliResult, FtdDeviceCliResponse
from cisco_sccfm_core.services.inventory.ftd_cli_service import (
    FtdCommandLineService,
    _build_fmc_uid_map,
    _extract_download_url,
    _parse_bulk_report,
)

FMC_UID = "09590f30-8cb7-11f0-a508-8e9f8a6273f4"
SCC_UID = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
DOMAIN_UID = "e276abec-e0f2-11e3-8169-6d9ed49b625f"


def _make_device(uid: str = SCC_UID, fmc_uid: str = FMC_UID) -> Device:
    fmc_info = MagicMock()
    fmc_info.fmc_device_record_uid = fmc_uid
    return Device(
        uid=uid,
        name="test-ftd-1",
        cdFmcInfo={"fmcDeviceRecordUid": fmc_uid},
    )


def _make_device_with_mock_info(uid: str = SCC_UID, fmc_uid: str = FMC_UID) -> MagicMock:
    device = MagicMock(spec=Device)
    device.uid = uid
    device.name = "test-ftd-1"
    device.device_record_on_fmc = MagicMock()
    device.device_record_on_fmc.uid = fmc_uid
    return device


SAMPLE_BULK_RESPONSE = {
    "devices": [FMC_UID],
    "command": "show failover",
    "metadata": {
        "task": {
            "name": "EXECUTE_BULK_COMMANDS",
            "id": "30064921167",
        }
    },
    "type": "BulkCommand",
}

SAMPLE_TASK_DONE = {
    "id": "30064921167",
    "taskType": "EXECUTE_BULK_COMMANDS",
    "status": "SUCCESS",
    "message": "Bulk command execution completed.",
    "metadata": {
        "downloadUrl": "https://api.int.security.cisco.com/firewall/v1/cdfmc/download/30064921167"
    },
}

SAMPLE_TASK_RUNNING = {
    "id": "30064921167",
    "status": "RUNNING",
    "message": "In progress",
}

SAMPLE_DOWNLOAD_BODY = {
    "command": "show failover",
    "deviceResponse": [
        {
            "deviceUUID": FMC_UID,
            "deviceName": "test-ftd-1",
            "response": "Failover Off\nFailover unit Secondary\n",
            "isError": False,
        }
    ],
}

SAMPLE_DOWNLOAD_ERROR = {
    "command": "show version",
    "deviceResponse": [
        {
            "deviceUUID": FMC_UID,
            "deviceName": "test-ftd-1",
            "response": None,
            "isError": True,
            "errorMsg": "Error on Management Center.",
        }
    ],
}


# ------------------------------------------------------------------
# Pure function tests
# ------------------------------------------------------------------


class TestBuildFmcUidMap:
    def test_maps_fmc_uid_to_scc_uid(self) -> None:
        device = _make_device_with_mock_info()
        result = _build_fmc_uid_map([device])
        assert result == {FMC_UID: SCC_UID}

    def test_falls_back_to_cd_fmc_info_uid(self) -> None:
        device = MagicMock(spec=Device)
        device.uid = SCC_UID
        device.cd_fmc_info = MagicMock()
        device.cd_fmc_info.fmc_device_record_uid = FMC_UID
        result = _build_fmc_uid_map([device])
        assert result == {FMC_UID: SCC_UID}

    def test_skips_device_without_fmc_info(self) -> None:
        device = MagicMock(spec=Device)
        device.uid = SCC_UID
        device.device_record_on_fmc = None
        result = _build_fmc_uid_map([device])
        assert result == {}

    def test_skips_device_without_fmc_record_uid(self) -> None:
        device = MagicMock(spec=Device)
        device.uid = SCC_UID
        device.device_record_on_fmc = MagicMock()
        device.device_record_on_fmc.uid = None
        result = _build_fmc_uid_map([device])
        assert result == {}


class TestExtractDownloadUrl:
    def test_extracts_url(self) -> None:
        url = _extract_download_url(SAMPLE_TASK_DONE)
        metadata = SAMPLE_TASK_DONE["metadata"]
        assert isinstance(metadata, dict)
        assert url == metadata["downloadUrl"]

    def test_raises_when_no_url(self) -> None:
        with pytest.raises(ValueError, match="no download URL"):
            _extract_download_url({"status": "SUCCESS", "metadata": {}})


class TestParseBulkReport:
    def test_parses_success(self) -> None:
        result = _parse_bulk_report(SAMPLE_DOWNLOAD_BODY)
        assert result.command == "show failover"
        assert len(result.device_responses) == 1
        resp = result.device_responses[0]
        assert resp.device_uuid == FMC_UID
        assert resp.device_name == "test-ftd-1"
        assert resp.is_error is False
        assert "Failover Off" in (resp.response or "")

    def test_parses_error_response(self) -> None:
        result = _parse_bulk_report(SAMPLE_DOWNLOAD_ERROR)
        assert len(result.device_responses) == 1
        resp = result.device_responses[0]
        assert resp.is_error is True
        assert resp.error_msg == "Error on Management Center."
        assert resp.response is None


# ------------------------------------------------------------------
# Service integration tests (mocked HTTP)
# ------------------------------------------------------------------


def _make_cdfmc_manager(domain_uid: str = DOMAIN_UID) -> Device:
    return Device(
        uid="mgr-uid",
        name="cdfmc-manager",
        deviceType=EntityType.CDFMC,
        fmcDomainUid=domain_uid,
    )


@pytest.fixture
def mock_deps(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    monkeypatch.setattr(
        "cisco_sccfm_core.services.inventory.ftd_cli_service.ApiClientFactory",
        MagicMock(),
    )
    mock_inv_svc = MagicMock()
    monkeypatch.setattr(
        "cisco_sccfm_core.services.inventory.ftd_cli_service.InventoryService",
        lambda config: mock_inv_svc,
    )
    return {"inventory_service": mock_inv_svc}


@pytest.fixture
def config() -> MagicMock:
    cfg = MagicMock()
    cfg.region = "us"
    cfg.api_token = "test-token"
    return cfg


@pytest.fixture
def service(mock_deps: dict[str, MagicMock], config: MagicMock) -> FtdCommandLineService:
    return FtdCommandLineService(config=config)


class TestGetCdfmcDomainUid:
    def test_returns_host_from_manager(
        self, service: FtdCommandLineService, mock_deps: dict[str, MagicMock]
    ) -> None:
        manager = _make_cdfmc_manager()
        mock_deps["inventory_service"].get_managers.return_value = DevicePage(
            count=1, limit=1, offset=0, items=[manager]
        )
        result = service._get_cdfmc_domain_uid()
        assert result == DOMAIN_UID

    def test_raises_when_no_managers(
        self, service: FtdCommandLineService, mock_deps: dict[str, MagicMock]
    ) -> None:
        mock_deps["inventory_service"].get_managers.return_value = DevicePage(
            count=0, limit=1, offset=0, items=[]
        )
        with pytest.raises(ValueError, match="No cdFMC manager"):
            service._get_cdfmc_domain_uid()


class TestExecuteCli:
    def test_rejects_non_show_command(
        self,
        service: FtdCommandLineService,
    ) -> None:
        with pytest.raises(ValueError, match="Only show commands are supported"):
            service.execute_cli(devices=[], command="configure network ipv4 manual")

    def test_full_flow(
        self,
        service: FtdCommandLineService,
        mock_deps: dict[str, MagicMock],
    ) -> None:
        manager = _make_cdfmc_manager()
        mock_deps["inventory_service"].get_managers.return_value = DevicePage(
            count=1, limit=1, offset=0, items=[manager]
        )

        device = _make_device_with_mock_info()

        http_responses: list[dict[str, Any]] = [
            SAMPLE_BULK_RESPONSE,  # submit
            SAMPLE_TASK_DONE,  # poll
            SAMPLE_DOWNLOAD_BODY,  # download
        ]
        call_idx = {"i": 0}

        def fake_http(self_inner: Any, *, url: str, **kwargs: Any) -> dict[str, Any]:
            idx = call_idx["i"]
            call_idx["i"] += 1
            return http_responses[idx]

        with patch.object(FtdCommandLineService, "_http_request", fake_http):
            result = service.execute_cli(
                devices=[device],
                command="show failover",
                polling_interval_sec=0,
            )

        assert isinstance(result, FtdBulkCliResult)
        assert result.command == "show failover"
        assert len(result.device_responses) == 1
        assert result.device_responses[0].is_error is False

    def test_returns_empty_when_no_fmc_uids(
        self,
        service: FtdCommandLineService,
        mock_deps: dict[str, MagicMock],
    ) -> None:
        manager = _make_cdfmc_manager()
        mock_deps["inventory_service"].get_managers.return_value = DevicePage(
            count=1, limit=1, offset=0, items=[manager]
        )

        device_no_fmc = MagicMock(spec=Device)
        device_no_fmc.uid = SCC_UID
        device_no_fmc.device_record_on_fmc = None

        result = service.execute_cli(devices=[device_no_fmc], command="show version")
        assert result.command == "show version"
        assert result.device_responses == []

    def test_polls_until_done(
        self,
        service: FtdCommandLineService,
        mock_deps: dict[str, MagicMock],
    ) -> None:
        manager = _make_cdfmc_manager()
        mock_deps["inventory_service"].get_managers.return_value = DevicePage(
            count=1, limit=1, offset=0, items=[manager]
        )

        device = _make_device_with_mock_info()

        http_responses: list[dict[str, Any]] = [
            SAMPLE_BULK_RESPONSE,  # submit
            SAMPLE_TASK_RUNNING,  # poll 1 — still running
            SAMPLE_TASK_DONE,  # poll 2 — done
            SAMPLE_DOWNLOAD_BODY,  # download
        ]
        call_idx = {"i": 0}

        def fake_http(self_inner: Any, *, url: str, **kwargs: Any) -> dict[str, Any]:
            idx = call_idx["i"]
            call_idx["i"] += 1
            return http_responses[idx]

        poll_statuses: list[str] = []

        with patch.object(FtdCommandLineService, "_http_request", fake_http):
            result = service.execute_cli(
                devices=[device],
                command="show failover",
                polling_interval_sec=0,
                on_poll=lambda s: poll_statuses.append(s),
            )

        assert isinstance(result, FtdBulkCliResult)
        assert poll_statuses == ["RUNNING", "SUCCESS"]

    def test_timeout_raises(
        self,
        service: FtdCommandLineService,
        mock_deps: dict[str, MagicMock],
    ) -> None:
        manager = _make_cdfmc_manager()
        mock_deps["inventory_service"].get_managers.return_value = DevicePage(
            count=1, limit=1, offset=0, items=[manager]
        )

        device = _make_device_with_mock_info()

        http_responses: list[dict[str, Any]] = [SAMPLE_BULK_RESPONSE, SAMPLE_TASK_RUNNING]
        call_idx = {"i": 0}

        def fake_http(self_inner: Any, *, url: str, **kwargs: Any) -> dict[str, Any]:
            idx = min(call_idx["i"], len(http_responses) - 1)
            call_idx["i"] += 1
            return http_responses[idx]

        with (
            patch.object(FtdCommandLineService, "_http_request", fake_http),
            pytest.raises(TimeoutError, match="did not complete"),
        ):
            service.execute_cli(
                devices=[device],
                command="show version",
                polling_interval_sec=0,
                timeout_sec=0,
            )

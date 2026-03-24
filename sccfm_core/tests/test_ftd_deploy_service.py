"""Tests for FtdDeployService."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from scc_firewall_manager_sdk import CdoTransaction

from sccfm_core.services.inventory.ftd_deploy_service import FtdDeployService


@pytest.fixture
def mock_inventory_api(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock_api = MagicMock()
    monkeypatch.setattr(
        "sccfm_core.services.inventory.ftd_deploy_service.ApiClientFactory",
        MagicMock(),
    )
    monkeypatch.setattr(
        "sccfm_core.services.inventory.ftd_deploy_service.InventoryApi",
        lambda client: mock_api,
    )
    return mock_api


@pytest.fixture
def service(mock_inventory_api: MagicMock) -> FtdDeployService:
    config = MagicMock()
    config.region = "us"
    config.api_token = "test-token"
    return FtdDeployService(config=config)


SAMPLE_TRANSACTION = CdoTransaction(transactionUid="txn-001")

UID_1 = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
UID_2 = "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"


class TestDeploySingle:
    def test_should_call_deploy_ftd_device_changes(
        self, service: FtdDeployService, mock_inventory_api: MagicMock
    ) -> None:
        mock_inventory_api.deploy_ftd_device_changes.return_value = SAMPLE_TRANSACTION

        result = service.deploy_single(device_uid=UID_1)

        assert result == SAMPLE_TRANSACTION
        mock_inventory_api.deploy_ftd_device_changes.assert_called_once()
        call_kwargs = mock_inventory_api.deploy_ftd_device_changes.call_args[1]
        assert call_kwargs["device_uid"] == UID_1
        deployment_input = call_kwargs["ftd_deployment_input"]
        assert deployment_input.deployment_notes is None
        assert deployment_input.description is None
        assert deployment_input.ignore_warnings is False

    def test_should_pass_optional_params(
        self, service: FtdDeployService, mock_inventory_api: MagicMock
    ) -> None:
        mock_inventory_api.deploy_ftd_device_changes.return_value = SAMPLE_TRANSACTION

        result = service.deploy_single(
            device_uid=UID_1,
            deployment_notes="Ticket-123",
            description="Policy update",
            ignore_warnings=True,
        )

        assert result == SAMPLE_TRANSACTION
        call_kwargs = mock_inventory_api.deploy_ftd_device_changes.call_args[1]
        deployment_input = call_kwargs["ftd_deployment_input"]
        assert deployment_input.deployment_notes == "Ticket-123"
        assert deployment_input.description == "Policy update"
        assert deployment_input.ignore_warnings is True

    def test_should_validate_uid(self, service: FtdDeployService) -> None:
        with pytest.raises(ValueError):
            service.deploy_single(device_uid="")


class TestDeployMultiple:
    def test_should_call_deploy_multiple_ftd_devices(
        self, service: FtdDeployService, mock_inventory_api: MagicMock
    ) -> None:
        mock_inventory_api.deploy_changes_to_multiple_ftd_devices.return_value = (
            SAMPLE_TRANSACTION
        )

        result = service.deploy_multiple(device_uids=[UID_1, UID_2])

        assert result == SAMPLE_TRANSACTION
        mock_inventory_api.deploy_changes_to_multiple_ftd_devices.assert_called_once()
        call_kwargs = (
            mock_inventory_api.deploy_changes_to_multiple_ftd_devices.call_args[1]
        )
        deployment_input = call_kwargs["ftd_multi_device_deployment_input"]
        assert deployment_input.device_uids == [UID_1, UID_2]
        assert deployment_input.deployment_notes is None
        assert deployment_input.description is None
        assert deployment_input.ignore_warnings is False

    def test_should_pass_optional_params(
        self, service: FtdDeployService, mock_inventory_api: MagicMock
    ) -> None:
        mock_inventory_api.deploy_changes_to_multiple_ftd_devices.return_value = (
            SAMPLE_TRANSACTION
        )

        result = service.deploy_multiple(
            device_uids=[UID_1, UID_2],
            deployment_notes="Bulk deploy",
            description="Weekend maintenance",
            ignore_warnings=True,
        )

        assert result == SAMPLE_TRANSACTION
        call_kwargs = (
            mock_inventory_api.deploy_changes_to_multiple_ftd_devices.call_args[1]
        )
        deployment_input = call_kwargs["ftd_multi_device_deployment_input"]
        assert deployment_input.deployment_notes == "Bulk deploy"
        assert deployment_input.description == "Weekend maintenance"
        assert deployment_input.ignore_warnings is True

    def test_should_validate_uids(self, service: FtdDeployService) -> None:
        with pytest.raises(ValueError):
            service.deploy_multiple(device_uids=[])

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for cisco_sccfm_core.services.inventory.asa_config_read_service module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from scc_firewall_manager_sdk import BulkOperationAsaDeviceRequest, CdoTransaction

from cisco_sccfm_core.services.inventory.asa_config_read_service import AsaConfigReadService

_UID_1 = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
_UID_2 = "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"


@pytest.fixture
def mock_config() -> MagicMock:
    config = MagicMock()
    config.region = "us"
    config.api_token = "test-token"
    return config


@pytest.fixture
def read_service(mock_config: MagicMock) -> AsaConfigReadService:
    with patch("cisco_sccfm_core.services.inventory.asa_config_read_service.ApiClientFactory"):
        return AsaConfigReadService(config=mock_config)


def _fake_transaction(uid: str) -> CdoTransaction:
    return CdoTransaction(transactionUid=uid, cdoTransactionStatus="PENDING")


def test_should_read_single_device_with_single_device_endpoint(
    read_service: AsaConfigReadService, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_read = MagicMock(return_value=_fake_transaction("txn-single"))
    mock_bulk = MagicMock()
    monkeypatch.setattr(read_service._inventory_api, "read_asa_device_configuration", mock_read)
    monkeypatch.setattr(
        read_service._inventory_api, "bulk_read_asa_device_configurations", mock_bulk
    )

    result = read_service.read_configuration(device_uids=[_UID_1])

    assert result.transaction_uid == "txn-single"
    mock_read.assert_called_once_with(device_uid=_UID_1)
    mock_bulk.assert_not_called()


def test_should_read_multiple_devices_with_bulk_endpoint(
    read_service: AsaConfigReadService, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_read = MagicMock()
    mock_bulk = MagicMock(return_value=_fake_transaction("txn-bulk"))
    monkeypatch.setattr(read_service._inventory_api, "read_asa_device_configuration", mock_read)
    monkeypatch.setattr(
        read_service._inventory_api, "bulk_read_asa_device_configurations", mock_bulk
    )

    result = read_service.read_configuration(device_uids=[_UID_1, _UID_2])

    assert result.transaction_uid == "txn-bulk"
    mock_read.assert_not_called()
    request: BulkOperationAsaDeviceRequest = mock_bulk.call_args.kwargs[
        "bulk_operation_asa_device_request"
    ]
    assert request.device_uids == [_UID_1, _UID_2]


def test_should_reject_invalid_uid(read_service: AsaConfigReadService) -> None:
    with pytest.raises(ValueError):
        read_service.read_configuration(device_uids=["not-a-uuid"])

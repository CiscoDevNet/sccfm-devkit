# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import cast
from unittest.mock import Mock

from scc_firewall_manager_sdk import AsaCreateOrUpdateInput, CdoTransaction, ConnectorType, Device

from cisco_sccfm_core.constants import ONBOARD_POLLING_INTERVAL_SEC
from cisco_sccfm_core.services.inventory.asa_onboard_service import AsaOnboardService


def test_onboard_asa_waits_for_transaction_and_fetches_device() -> None:
    service = AsaOnboardService.__new__(AsaOnboardService)
    service.inventory_api = Mock()
    service.transaction_service = Mock()

    expected_device = Device(uid="device-1", name="asa-1", deviceType="ASA")
    service.inventory_api.onboard_asa_device.return_value = CdoTransaction(transactionUid="txn-1")
    service.transaction_service.wait_for_transaction_to_finish.return_value = CdoTransaction(
        transactionUid="txn-1",
        cdoTransactionStatus="DONE",
        entityUid="device-1",
    )
    service.inventory_api.get_device.return_value = expected_device

    result = service.onboard_asa(cast(AsaCreateOrUpdateInput, Mock()))

    assert result is expected_device
    service.transaction_service.wait_for_transaction_to_finish.assert_called_once_with(
        transaction_uid="txn-1",
        polling_interval_sec=ONBOARD_POLLING_INTERVAL_SEC,
    )
    service.inventory_api.get_device.assert_called_once_with(device_uid="device-1")


def test_onboard_asa_with_new_policy_view_sends_ui_device_metadata() -> None:
    service = AsaOnboardService.__new__(AsaOnboardService)
    service.inventory_api = Mock()
    service.transaction_service = Mock()
    api_client = service.inventory_api.api_client
    api_client.param_serialize.return_value = ("POST", "url", {}, "body", [])
    api_client.response_deserialize.return_value = Mock(data=CdoTransaction(transactionUid="txn-1"))
    service.transaction_service.wait_for_transaction_to_finish.return_value = CdoTransaction(
        transactionUid="txn-1", cdoTransactionStatus="DONE", entityUid="device-1"
    )
    asa_input = AsaCreateOrUpdateInput(
        name="asa-1",
        deviceAddress="198.51.100.1:443",
        username="admin",
        password="secret",
        connectorType=ConnectorType.CDG,
        ignoreCertificate=True,
    )

    service.onboard_asa(asa_input, new_policy_view=True)

    service.inventory_api.onboard_asa_device.assert_not_called()
    serialize_kwargs = api_client.param_serialize.call_args.kwargs
    assert serialize_kwargs["method"] == "POST"
    assert serialize_kwargs["resource_path"] == "/v1/inventory/devices/asas"
    assert serialize_kwargs["body"] == {
        **asa_input.to_dict(),
        "metadata": {"isNewPolicyObjectModel": "true"},
    }
    api_client.call_api.assert_called_once_with("POST", "url", {}, "body", [])
    service.inventory_api.get_device.assert_called_once_with(device_uid="device-1")

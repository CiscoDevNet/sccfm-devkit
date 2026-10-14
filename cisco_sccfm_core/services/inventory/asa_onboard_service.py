# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import cast

from scc_firewall_manager_sdk import AsaCreateOrUpdateInput, CdoTransaction, Device, InventoryApi

from cisco_sccfm_core import ApiClientFactory
from cisco_sccfm_core.constants import ONBOARD_POLLING_INTERVAL_SEC
from cisco_sccfm_core.models.cdo_transaction_status import CdoTransactionStatus
from cisco_sccfm_core.services.transaction_service import TransactionService
from cisco_sccfm_core.types import ConfigLike

# The SCCFM UI creates ASAs with this device metadata so they use the New ASA
# Policy View; without it the access-groups API never lists their ACLs.
_NEW_POLICY_VIEW_METADATA = {"isNewPolicyObjectModel": "true"}


class AsaOnboardService:
    def __init__(self, config: ConfigLike) -> None:
        self.inventory_api = InventoryApi(ApiClientFactory().build(config=config))
        self.transaction_service = TransactionService(config=config)

    def onboard_asa(
        self, asa_create_or_update_input: AsaCreateOrUpdateInput, *, new_policy_view: bool = False
    ) -> Device:
        transaction: CdoTransaction = (
            self._onboard_with_new_policy_view(asa_create_or_update_input)
            if new_policy_view
            else self.inventory_api.onboard_asa_device(
                asa_create_or_update_input=asa_create_or_update_input
            )
        )
        completed_transaction: CdoTransaction = (
            self.transaction_service.wait_for_transaction_to_finish(
                transaction_uid=transaction.transaction_uid,
                polling_interval_sec=ONBOARD_POLLING_INTERVAL_SEC,
            )
        )
        if completed_transaction.cdo_transaction_status != CdoTransactionStatus.DONE:
            error_msg = (
                f"Transaction {completed_transaction.transaction_uid} failed with status "
                f"{completed_transaction.cdo_transaction_status}"
            )
            if completed_transaction.error_message:
                error_msg += f": {completed_transaction.error_message}"
            if completed_transaction.error_details:
                error_msg += f" (details: {completed_transaction.error_details})"
            raise Exception(error_msg)

        return self.inventory_api.get_device(device_uid=completed_transaction.entity_uid)

    def _onboard_with_new_policy_view(
        self, asa_create_or_update_input: AsaCreateOrUpdateInput
    ) -> CdoTransaction:
        """Send the onboarding request with the device metadata the UI sends.

        AsaCreateOrUpdateInput has no metadata field and would drop it, so build
        the same request as InventoryApi.onboard_asa_device from a plain body.
        """
        api_client = self.inventory_api.api_client
        request = api_client.param_serialize(
            method="POST",
            resource_path="/v1/inventory/devices/asas",
            header_params={"Accept": "application/json", "Content-Type": "application/json"},
            body={**asa_create_or_update_input.to_dict(), "metadata": _NEW_POLICY_VIEW_METADATA},
            auth_settings=["bearerAuth"],
        )
        response = api_client.call_api(*request)
        response.read()
        return cast(
            CdoTransaction,
            api_client.response_deserialize(
                response_data=response, response_types_map={"202": "CdoTransaction"}
            ).data,
        )

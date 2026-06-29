# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import time

from scc_firewall_manager_sdk import (
    CdoTransaction,
    ConnectivityState,
    Device,
    FtdRegistrationInput,
    InventoryApi,
)

from sccfm_core import ApiClientFactory
from sccfm_core.constants import ONBOARD_POLLING_INTERVAL_SEC
from sccfm_core.models.cdo_transaction_status import CdoTransactionStatus
from sccfm_core.services.transaction_service import TransactionService
from sccfm_core.types import ConfigLike

_ONLINE_POLL_INTERVAL_SEC = 30
_ONLINE_TIMEOUT_SEC = 1800


class FtdRegisterService:
    def __init__(self, config: ConfigLike) -> None:
        self.inventory_api = InventoryApi(ApiClientFactory().build(config=config))
        self.transaction_service = TransactionService(config=config)

    def register_ftd(self, ftd_uid: str, skip_initial_deployment: bool = False) -> Device:
        transaction: CdoTransaction = self.inventory_api.finish_onboarding_ftd_device(
            ftd_registration_input=FtdRegistrationInput(
                ftdUid=ftd_uid,
                skipInitialDeployment=skip_initial_deployment,
            )
        )
        completed_transaction: CdoTransaction = (
            self.transaction_service.wait_for_transaction_to_finish(
                transaction_uid=transaction.transaction_uid,
                polling_interval_sec=ONBOARD_POLLING_INTERVAL_SEC,
            )
        )
        if completed_transaction.cdo_transaction_status != CdoTransactionStatus.DONE:
            raise Exception(
                f"Transaction {completed_transaction.transaction_uid} failed with status "
                f"{completed_transaction.cdo_transaction_status}"
            )

        return self._wait_for_online(device_uid=completed_transaction.entity_uid)

    def _wait_for_online(self, device_uid: str) -> Device:
        deadline = time.monotonic() + _ONLINE_TIMEOUT_SEC
        while time.monotonic() < deadline:
            device = self.inventory_api.get_device(device_uid=device_uid)
            if device.connectivity_state == ConnectivityState.ONLINE:
                return device
            time.sleep(_ONLINE_POLL_INTERVAL_SEC)
        raise TimeoutError(
            f"Device {device_uid} did not reach ONLINE state within {_ONLINE_TIMEOUT_SEC}s"
        )

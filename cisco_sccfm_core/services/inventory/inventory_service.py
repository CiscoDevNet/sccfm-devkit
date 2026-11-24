# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from scc_firewall_manager_sdk import CdoTransaction, Device, DevicePage, InventoryApi

from cisco_sccfm_core.factories import ApiClientFactory
from cisco_sccfm_core.types import ConfigLike
from cisco_sccfm_core.utils import validate_uids


class InventoryService:
    def __init__(self, config: ConfigLike) -> None:
        api_client = ApiClientFactory().build(config)
        self.inventory_api = InventoryApi(api_client)

    def get_devices(self, *, limit: int, offset: int, query: str | None) -> DevicePage:
        return self.inventory_api.get_devices(limit=str(limit), offset=str(offset), q=query)

    def get_device_by_uid(self, device_uid: str) -> Device:
        return self.inventory_api.get_device(device_uid=device_uid)

    def get_managers(self, *, limit: int, offset: int, query: str | None = None) -> DevicePage:
        return self.inventory_api.get_device_managers(limit=str(limit), offset=str(offset), q=query)

    def read_asa_device_configuration(self, device_uid: str) -> CdoTransaction:
        """Trigger CDO to re-read *device_uid*'s live running-config on demand.

        API equivalent of the CDO UI's "Sync"/"accept out-of-band changes"
        action on a device's page - the same thing a human has to click
        after pushing config directly via CLI (e.g. execute_asa_cli) before
        CDO's own cached model, device-role auto-detection (e.g.
        ASA_RA_VPN_HEADEND), and any UI picker reading off that cached
        model reflect the change. Without this, the tenant's background
        out-of-band conflict-detection poll would eventually pick it up
        instead (ConflictDetectionInterval - defaults to every 6 hours).

        Returns the CdoTransaction immediately (fire-and-forget) - same
        pattern as AsaUpgradeService/AsaSecureClientService.push_package;
        callers that need to block use
        TransactionService.wait_for_transaction_to_finish themselves.
        """
        validate_uids([device_uid])
        return self.inventory_api.read_asa_device_configuration(device_uid=device_uid)

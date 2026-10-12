# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from scc_firewall_manager_sdk import BulkOperationAsaDeviceRequest, CdoTransaction, InventoryApi

from cisco_sccfm_core.factories import ApiClientFactory
from cisco_sccfm_core.types import ConfigLike
from cisco_sccfm_core.utils import validate_uids


class AsaConfigReadService:
    """Reads the running configuration of ASA devices into SCC Firewall Manager.

    SCC Firewall Manager does not re-read a device after a change made outside it,
    such as a CLI push, so its copy of the configuration (access groups, rules,
    objects) stays stale until a read. A read replaces that copy, so changes staged
    in SCC Firewall Manager but not yet deployed can be lost.
    """

    def __init__(self, config: ConfigLike) -> None:
        self._inventory_api = InventoryApi(ApiClientFactory().build(config=config))

    def read_configuration(self, *, device_uids: list[str]) -> CdoTransaction:
        """Start a configuration read and return the :class:`CdoTransaction` tracking it."""
        validate_uids(device_uids)
        if len(device_uids) == 1:
            return self._inventory_api.read_asa_device_configuration(device_uid=device_uids[0])
        return self._inventory_api.bulk_read_asa_device_configurations(
            bulk_operation_asa_device_request=BulkOperationAsaDeviceRequest(deviceUids=device_uids)
        )

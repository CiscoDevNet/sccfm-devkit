# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Remove CLI registration-test FTD records before and after the suite."""

from __future__ import annotations

import time

from scc_firewall_manager_sdk import InventoryApi
from scc_firewall_manager_sdk.exceptions import ApiException

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e.ftd.phases.test_data import (
    FTD_CLEANUP_RETRIES,
    FTD_REGISTRATION_DELAY_SEC,
    FTD_REGISTRATION_HOST,
    FTD_REGISTRATION_NAME,
    validate_registration_name,
)
from sccfm_cli.services import ConfigService
from sccfm_core.factories import ApiClientFactory


def _registration_query() -> str:
    escaped_name = FTD_REGISTRATION_NAME.replace("\\", "\\\\").replace('"', '\\"')
    return f'deviceType:CDFMC_MANAGED_FTD AND name:"{escaped_name}"'


def _matching_devices(api: InventoryApi) -> list[object]:
    page = api.get_devices(limit="50", offset="0", q=_registration_query())
    return [
        device
        for device in page.items or []
        if getattr(device, "name", None) == FTD_REGISTRATION_NAME
    ]


def run(ctx: ProfileContext) -> None:
    if not FTD_REGISTRATION_HOST:
        return
    validate_registration_name()
    config = ConfigService(path=ctx.config_path).load(ctx.profile)
    if config is None:
        raise AssertionError(f"E2E profile {ctx.profile!r} was not found at {ctx.config_path}")

    api = InventoryApi(ApiClientFactory.build(config))
    for device in _matching_devices(api):
        uid = getattr(device, "uid", None)
        if not uid:
            raise AssertionError(f"Registration-test FTD {FTD_REGISTRATION_NAME!r} has no UID")
        try:
            api.delete_cd_fmc_managed_ftd_device(device_uid=uid)
        except ApiException as exc:
            if exc.status != 404:
                raise

    for _ in range(FTD_CLEANUP_RETRIES):
        if not _matching_devices(api):
            return
        time.sleep(FTD_REGISTRATION_DELAY_SEC)

    raise AssertionError(
        f"FTD {FTD_REGISTRATION_NAME!r} still exists after " f"{FTD_CLEANUP_RETRIES} cleanup checks"
    )

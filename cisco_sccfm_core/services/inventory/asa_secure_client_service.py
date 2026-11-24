# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from scc_firewall_manager_sdk import (
    CdoTransaction,
    CompatibleSecureClientVersionDto,
    SecureClientManagementApi,
    SecureClientPackageDto,
    SecureClientPlatformDto,
    TriggerSecureClientUpgradeInput,
)

from cisco_sccfm_core.factories import ApiClientFactory
from cisco_sccfm_core.types import ConfigLike
from cisco_sccfm_core.utils import validate_uids


class AsaSecureClientService:
    """Looks up and pushes Secure Client (AnyConnect) packages to ASA devices
    directly from CDO's own package catalog.

    This is the same mechanism behind CDO's "AnyConnect Packages Detected"
    RAVPN wizard step - no local .pkg file, no disk0: upload, no reachable
    download/mirror server needed on our side. CDO's backend owns the actual
    package bits and stages them onto the device itself once triggered - a
    fundamentally different path from AsaDiskFileService (which parses
    `dir disk0:` CLI output for files staged some other way, e.g. manually
    copied).

    NOT YET VERIFIED against the live SDK: `scc_firewall_manager_sdk` was
    not importable in the sandbox this was written in (no network egress,
    package not installed anywhere reachable). Every class/method name
    below follows this SDK's established codegen convention exactly - the
    OpenAPI tag "Secure Client Management" mirrors how "Device Upgrades"
    became `DeviceUpgradesApi` (see asa_upgrade_version_service.py /
    asa_upgrade_service.py, the direct precedent this file mirrors), and
    operationIds getAsaCompatibleSecureClientVersions /
    triggerSecureClientUpgrade / getAsaSecureClientPackages convert to
    snake_case the same way get_asa_upgrade_versions /
    upgrade_asa_device(s) already do elsewhere in this codebase. If this
    service raises an ImportError or AttributeError on first real use,
    checking the actual installed SDK's class/method names is the first
    thing to do - see cdo-public-api-docs/openapi.yaml paths
    `/v1/inventory/devices/asas/secure-client/upgrades/versions`,
    `/v1/inventory/devices/asas/secure-client/upgrades`, and
    `/v1/inventory/devices/asas/{deviceUid}/secure-client/packages` for the
    underlying contract this is meant to wrap.
    """

    def __init__(self, config: ConfigLike) -> None:
        self._secure_client_api = SecureClientManagementApi(
            ApiClientFactory().build(config=config)
        )

    def get_compatible_versions(
        self,
        device_uids: list[str],
        limit: int = 50,
        offset: int = 0,
    ) -> list[CompatibleSecureClientVersionDto]:
        """Return Secure Client versions CDO's catalog can push to every
        device in *device_uids* - the same catalog the CDO UI's package
        dropdown is backed by.

        Unlike AsaUpgradeVersionService.get_compatible_versions (ASA
        firmware), this REST endpoint accepts every device UID in a single
        call and the API itself returns only versions already compatible
        across all of them - no client-side intersection needed here.
        """
        validate_uids(device_uids)
        page = self._secure_client_api.get_asa_compatible_secure_client_versions(
            device_uids=device_uids,
            limit=limit,
            offset=offset,
        )
        return list(page.items or [])

    def list_installed_packages(
        self,
        device_uid: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SecureClientPackageDto]:
        """Return Secure Client packages CDO has already staged on
        *device_uid* via this same push path.

        REST analogue of AsaDiskFileService.list_disk_files's
        ANYCONNECT_PACKAGE classification, but scoped to what CDO itself
        tracks as pushed through this API - it may not see a package that
        was staged some other way (e.g. manually copied onto disk0:
        out of band), since that's a different tracking mechanism.
        """
        validate_uids([device_uid])
        page = self._secure_client_api.get_asa_secure_client_packages(
            device_uid=device_uid,
            limit=limit,
            offset=offset,
        )
        return list(page.items or [])

    def push_package(
        self,
        device_uids: list[str],
        version: str,
        platforms: list[SecureClientPlatformDto] | None = None,
        name: str | None = None,
    ) -> CdoTransaction:
        """Trigger CDO to push *version* from its own catalog onto every
        device in *device_uids*.

        If *platforms* is omitted, CDO pushes every platform (OS/CPU
        architecture combination) available for *version*. Returns the
        CdoTransaction tracking the async operation immediately - this
        does NOT wait for it to finish, same fire-and-forget-by-default
        pattern as AsaUpgradeService.upgrade_single/upgrade_multiple;
        callers that need to block use TransactionService.wait_for_transaction_to_finish
        on the returned transaction_uid themselves.
        """
        validate_uids(device_uids)
        push_input = TriggerSecureClientUpgradeInput(
            deviceUids=device_uids,
            version=version,
            platforms=platforms,
            name=name,
        )
        return self._secure_client_api.trigger_secure_client_upgrade(
            trigger_secure_client_upgrade_input=push_input,
        )


def pick_latest_version(
    versions: list[CompatibleSecureClientVersionDto],
) -> CompatibleSecureClientVersionDto | None:
    """Return the entry with the highest ``version`` string, or ``None`` if
    *versions* is empty.

    Secure Client version strings observed look like "5.1.15.287" or
    "4.10.05095" - purely dotted numeric, unlike ASA software versions
    (e.g. "7.18(1.152).openjre"), so a simple tuple-of-ints sort is
    sufficient here; no suffix-stripping like
    asa_upgrade_version_service._version_sort_key needs.
    """
    if not versions:
        return None

    def _sort_key(v: CompatibleSecureClientVersionDto) -> tuple[int, ...]:
        return tuple(int(part) for part in (v.version or "0").split("."))

    return max(versions, key=_sort_key)

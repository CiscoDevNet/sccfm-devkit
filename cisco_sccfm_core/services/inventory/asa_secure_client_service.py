# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from scc_firewall_manager_sdk import (
    ApiException,
    CdoTransaction,
    CompatibleSecureClientVersionDto,
    SecureClientManagementApi,
    SecureClientPackageDto,
    SecureClientPlatformDto,
    TriggerSecureClientUpgradeInput,
)

from cisco_sccfm_core.factories import ApiClientFactory
from cisco_sccfm_core.services.inventory.inventory_service import InventoryService
from cisco_sccfm_core.types import ConfigLike
from cisco_sccfm_core.utils import validate_uids

_T = TypeVar("_T")

# Confirmed live 2026-11-25 (CDO UI, hydra-asa-1): a device can show
# "Synced"/Online in CDO's device list while its Software Version column is
# still blank - i.e. sync_asa_device_config's own `wait: true` completing
# does NOT imply device.software_version has been populated yet. This is a
# SEPARATE, apparently slower settling step than the sync transaction
# itself, and it's the real reason get_compatible_versions 500s right after
# a sync even once _call_retrying_transient_server_errors' retries are
# added below - CDO's catalog lookup can't say what's compatible with a
# device whose own version it doesn't know yet, and a mere 5xx retry won't
# help if that population genuinely takes longer than the retry window.
# Mirrors FtdRegisterService._wait_for_online's poll-for-a-field pattern.
_SOFTWARE_VERSION_POLL_INTERVAL_SEC = 15.0
_SOFTWARE_VERSION_TIMEOUT_SEC = 600.0

# Observed live 2026-11-24/25 (see asa_ravpn_configure role + project memory):
# the beta "Secure Client Management" API backing this whole service is prone
# to bare 500 "Internal server error" responses with no further detail, most
# plausibly because CDO's backend hasn't fully finished settling a device's
# role/state right after a sync_asa_device_config call before this code asks
# it about compatible versions. A short linear-backoff retry is the cheapest
# way to ride that out, since CDO's error body gives us nothing else to act
# on. Only applied to the two read-only calls below (get_compatible_versions,
# list_installed_packages) - deliberately NOT to push_package(), which
# creates a transaction server-side; blindly retrying an ambiguous 5xx there
# risks double-triggering a push if the first attempt actually succeeded but
# the response was lost in transit.
_TRANSIENT_SERVER_ERROR_STATUSES = frozenset({500, 502, 503, 504})
_TRANSIENT_SERVER_ERROR_MAX_ATTEMPTS = 3
_TRANSIENT_SERVER_ERROR_BACKOFF_SEC = 5.0


def _call_retrying_transient_server_errors(call: Callable[[], _T]) -> _T:
    """Call *call*, retrying on a transient (5xx) ApiException with a linear
    backoff, up to _TRANSIENT_SERVER_ERROR_MAX_ATTEMPTS attempts total.

    Re-raises immediately on a non-5xx ApiException (e.g. 400/404 - a real
    client error, not worth retrying) or once attempts are exhausted.
    """
    for attempt in range(1, _TRANSIENT_SERVER_ERROR_MAX_ATTEMPTS + 1):
        try:
            return call()
        except ApiException as exc:
            status = getattr(exc, "status", None)
            if (
                status not in _TRANSIENT_SERVER_ERROR_STATUSES
                or attempt == _TRANSIENT_SERVER_ERROR_MAX_ATTEMPTS
            ):
                raise
            time.sleep(_TRANSIENT_SERVER_ERROR_BACKOFF_SEC * attempt)
    raise AssertionError("unreachable")  # loop above always returns or raises


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

    Class/method names verified live 2026-11-24: a Jenkins run reached
    get_asa_compatible_secure_client_versions and got back a real,
    structured CDO error body (errorCode SERVER_ERROR, requestId/tenantId/
    etc.) rather than an ImportError/AttributeError, confirming the SDK's
    method names below are correct - the 500 itself is a backend issue (see
    _call_retrying_transient_server_errors above), not a wrong-binding one.
    """

    def __init__(self, config: ConfigLike) -> None:
        self._config = config
        self._secure_client_api = SecureClientManagementApi(
            ApiClientFactory().build(config=config)
        )

    def wait_for_software_version(
        self,
        device_uids: list[str],
        timeout_sec: float = _SOFTWARE_VERSION_TIMEOUT_SEC,
        poll_interval_sec: float = _SOFTWARE_VERSION_POLL_INTERVAL_SEC,
    ) -> None:
        """Block until every device in *device_uids* reports a non-empty
        ``software_version`` via InventoryService, or raise TimeoutError.

        Call this BEFORE get_compatible_versions for devices that were just
        synced (cisco.sccfm.sync_asa_device_config) - see module-level
        comment above for why the sync's own completion doesn't guarantee
        this field is populated yet. A no-op (single pass, no sleep) if
        every device already has a version, which is the common case for
        devices that have been stable for a while.
        """
        inventory_service = InventoryService(config=self._config)
        deadline = time.monotonic() + timeout_sec
        pending = set(device_uids)
        while True:
            pending = {
                uid
                for uid in pending
                if not inventory_service.get_device_by_uid(device_uid=uid).software_version
            }
            if not pending:
                return
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Device(s) {sorted(pending)} did not report a software version "
                    f"within {timeout_sec}s - CDO's backend may still be settling "
                    f"device state after a recent config sync."
                )
            time.sleep(poll_interval_sec)

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
        # NOTE: limit/offset are typed as `string` (not integer) in this
        # specific beta endpoint's OpenAPI schema, unlike the equivalent
        # params on older/stable endpoints (e.g. InventoryService.get_devices)
        # - confirmed live 2026-11-24 when passing plain ints raised a
        # pydantic validation error from the SDK. Keep these str()'d even if
        # it looks redundant.
        page = _call_retrying_transient_server_errors(
            lambda: self._secure_client_api.get_asa_compatible_secure_client_versions(
                device_uids=device_uids,
                limit=str(limit),
                offset=str(offset),
            )
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
        # Same string-typed limit/offset quirk as get_compatible_versions above.
        page = _call_retrying_transient_server_errors(
            lambda: self._secure_client_api.get_asa_secure_client_packages(
                device_uid=device_uid,
                limit=str(limit),
                offset=str(offset),
            )
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

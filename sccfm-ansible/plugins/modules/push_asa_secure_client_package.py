# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

DOCUMENTATION = r"""
---
module: push_asa_secure_client_package
short_description: Push a Secure Client (AnyConnect) package to ASA devices from CDO's catalog
description:
  - Pushes a Secure Client / AnyConnect webdeploy package onto one or more
    ASA devices managed by SCC Firewall Manager, sourced directly from
    CDO's own package catalog - the same catalog backing CDO's
    "AnyConnect Packages Detected" RAVPN wizard step.
  - No local .pkg file, no manual upload to disk0, and no reachable
    download/mirror server is needed - CDO's backend owns the package bits
    and stages them onto the device itself.
  - If C(version) is omitted, the newest version in CDO's compatible-version
    catalog for the target device(s) is selected automatically.
  - Idempotent - if every target device already has a package matching the
    resolved version staged (as tracked by CDO through this same path), the
    module returns C(ok) (changed=False) without pushing again.
options:
  query:
    description:
      - Lucene query to select ASA devices.
      - Mutually exclusive with C(uids).
      - The query is automatically combined with C(deviceType:ASA).
    required: false
    type: str
  uids:
    description:
      - List of device UIDs to push the package to.
      - Mutually exclusive with C(query).
    required: false
    type: list
    elements: str
  limit:
    description:
      - Maximum number of devices to return when using C(query).
      - Ignored when using C(uids).
    required: false
    type: int
    default: 50
  offset:
    description:
      - Pagination offset when using C(query).
      - Ignored when using C(uids).
    required: false
    type: int
    default: 0
  version:
    description:
      - Secure Client version to push (e.g. C(5.1.15.287)).
      - Must be present in CDO's compatible-version catalog for the target
        device(s) (see C(cisco.sccfm.list_asa_secure_client_versions)).
      - If omitted, the newest compatible version is selected automatically.
    required: false
    type: str
  platforms:
    description:
      - Restrict the push to specific OS/CPU-architecture combinations.
      - Each entry is a dict with keys C(os) (one of C(LINUX), C(MACOS),
        C(WINDOWS)) and C(cpu_architecture) (one of C(ARM64), C(X86_64),
        C(UNIVERSAL)).
      - If omitted, every platform available for C(version) is pushed.
    required: false
    type: list
    elements: dict
  upgrade_name:
    description:
      - Human-readable name to identify and track the push/upgrade run.
    required: false
    type: str
  wait:
    description:
      - Wait for the returned push transaction to reach a terminal status.
      - When enabled, the module fails if the transaction ends in C(ERROR)
        or C(CANCELLED).
    required: false
    type: bool
    default: false
  timeout:
    description:
      - Maximum number of seconds to wait for the push transaction when
        C(wait=true).
    required: false
    type: int
    default: 3600
  profile:
    description: Named SCCFM profile configured by C(sccfm-cli configure).
    required: false
    type: str
    default: default
  config_path:
    description: Optional path to the canonical SCCFM profile configuration file.
    required: false
    type: path
author:
  - Cisco SCCFM Team (@CiscoDevNet)
"""

EXAMPLES = r"""
# Example 1: Push the newest compatible Secure Client version
- name: Push latest Secure Client package
  cisco.sccfm.push_asa_secure_client_package:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
    profile: default

# Example 2: Push a specific version using a query, and wait for completion
- name: Push a specific Secure Client version to branch ASAs
  cisco.sccfm.push_asa_secure_client_package:
    query: "name:branch-*"
    version: "5.1.15.287"
    wait: true
    timeout: 1800

# Example 3: Restrict to a single platform
- name: Push Linux-only Secure Client package
  cisco.sccfm.push_asa_secure_client_package:
    uids:
      - "uid-1"
    version: "5.1.15.287"
    platforms:
      - os: LINUX
        cpu_architecture: X86_64

# Example 4: Using module_defaults (recommended)
- name: Push Secure Client package
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Push latest Secure Client package to a device
      cisco.sccfm.push_asa_secure_client_package:
        uids:
          - "uid-1"
        wait: true
"""

RETURN = r"""
transaction:
  description: The triggered or completed transaction object for the push.
  returned: success (changed=True)
  type: dict
device_count:
  description: Number of devices the package was pushed to.
  returned: always
  type: int
resolved_version:
  description: The Secure Client version that was pushed (explicit or auto-selected).
  returned: success
  type: str
"""


from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import (
        ApiException,
        CdoTransaction,
        DevicePage,
        SecureClientPlatformDto,
    )

    from cisco_sccfm_core import ASA_DEVICE_TYPE_FILTER, InventoryService, SccApiError
    from cisco_sccfm_core.constants import DEFAULT_TRANSACTION_TIMEOUT_SEC
    from cisco_sccfm_core.models.cdo_transaction_status import CdoTransactionStatus
    from cisco_sccfm_core.services.inventory import AsaSecureClientService, pick_latest_version
    from cisco_sccfm_core.services.transaction_service import TransactionService
    from cisco_sccfm_core.types import ConfigLike
except ImportError as exc:
    record_import_error(exc)
    ApiException = RuntimeError
    NotFoundError = LookupError
    FtdConfigureManagerError = ValueError
    DEFAULT_TRANSACTION_TIMEOUT_SEC = 3600


from ..module_utils.config import Config, base_argument_spec, create_config


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
        "version": {"type": "str", "required": False},
        "platforms": {"type": "list", "elements": "dict", "required": False},
        "upgrade_name": {"type": "str", "required": False},
        "wait": {"type": "bool", "required": False, "default": False},
        "timeout": {
            "type": "int",
            "required": False,
            "default": DEFAULT_TRANSACTION_TIMEOUT_SEC,
        },
        **base_argument_spec(),
    }


def resolve_device_uids_from_query(
    config: ConfigLike,
    query: str,
    limit: int,
    offset: int,
) -> list[str]:
    """Resolve device UIDs from a Lucene query."""
    inventory_service = InventoryService(config=config)
    page: DevicePage = inventory_service.get_devices(
        limit=limit,
        offset=offset,
        query=f"({query}) AND {ASA_DEVICE_TYPE_FILTER}",
    )
    return [device.uid for device in (page.items or [])]


def _resolve_target_version(
    config: ConfigLike,
    device_uids: list[str],
    requested_version: str | None,
) -> str:
    """Return *requested_version* as-is, or auto-pick the newest compatible
    version from CDO's catalog if none was requested.

    Fails (raises ValueError) if the catalog has nothing compatible with
    every device in *device_uids* at all - mirrors the fail-fast behaviour
    the previous disk0:-based approach had for "no package available".
    """
    if requested_version:
        return requested_version

    secure_client_service = AsaSecureClientService(config=config)
    compatible = secure_client_service.get_compatible_versions(device_uids=device_uids)

    latest = pick_latest_version(compatible)
    if latest is None or not latest.version:
        raise ValueError(
            "No compatible Secure Client versions found in CDO's catalog for the "
            "specified device(s), and no version was explicitly set."
        )
    return latest.version


def _all_devices_have_version(
    config: ConfigLike,
    device_uids: list[str],
    version: str,
) -> bool:
    """Return True if every device already has *version* staged, per CDO's
    own package tracking for this push path."""
    secure_client_service = AsaSecureClientService(config=config)
    for uid in device_uids:
        installed = secure_client_service.list_installed_packages(device_uid=uid)
        if not any(pkg.version == version for pkg in installed):
            return False
    return True


def _build_platform_dtos(
    platforms: list[dict[str, Any]] | None,
) -> list[SecureClientPlatformDto] | None:
    if not platforms:
        return None
    return [
        SecureClientPlatformDto(
            os=p["os"],
            cpuArchitecture=p["cpu_architecture"],
        )
        for p in platforms
    ]


def _is_failed_transaction(transaction: CdoTransaction) -> bool:
    return transaction.cdo_transaction_status in {
        CdoTransactionStatus.ERROR,
        CdoTransactionStatus.CANCELLED,
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
        mutually_exclusive=[["query", "uids"]],
        required_one_of=[["query", "uids"]],
    )

    config: Config = create_config(module)

    uids: list[str] | None = module.params.get("uids")
    query: str | None = module.params.get("query")
    # Tracks which API call was in flight when an exception hit, so the
    # generic SERVER_ERROR/500s this beta API area is prone to say WHERE
    # they happened instead of just "Internal server error" - see
    # project memory on the 2026-11-24 live-run failures this was added
    # to diagnose.
    stage = "resolving device UIDs"

    try:
        if uids:
            device_uids = uids
        else:
            device_uids = resolve_device_uids_from_query(
                config=config,
                query=cast(str, query),
                limit=module.params["limit"],
                offset=module.params["offset"],
            )
            if not device_uids:
                module.fail_json(msg="No devices found matching the specified query.")

        stage = "resolving target Secure Client version (get_compatible_versions)"
        requested_version: str | None = module.params.get("version")
        target_version = _resolve_target_version(config, device_uids, requested_version)

        stage = "checking already-installed packages (list_installed_packages)"
        # Idempotency: skip if every device already has this version staged
        if _all_devices_have_version(config, device_uids, target_version):
            module.exit_json(
                changed=False,
                msg=f"All devices already have Secure Client version {target_version}.",
                device_count=len(device_uids),
                resolved_version=target_version,
            )

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Would push Secure Client version {target_version} to "
                f"{len(device_uids)} device(s).",
                device_count=len(device_uids),
                resolved_version=target_version,
                transaction={},
            )

        platforms = _build_platform_dtos(module.params.get("platforms"))
        upgrade_name: str | None = module.params.get("upgrade_name")
        wait_for_completion: bool = module.params.get("wait", False)
        timeout: int = module.params.get("timeout", DEFAULT_TRANSACTION_TIMEOUT_SEC)

        stage = "triggering the push (trigger_secure_client_upgrade)"
        secure_client_service = AsaSecureClientService(config=config)
        transaction = secure_client_service.push_package(
            device_uids=device_uids,
            version=target_version,
            platforms=platforms,
            name=upgrade_name,
        )

        if wait_for_completion:
            if transaction.transaction_uid is None:
                module.fail_json(msg="Transaction UID missing from push response.")

            stage = "waiting for the push transaction to finish"
            transaction = TransactionService(config=config).wait_for_transaction_to_finish(
                transaction_uid=transaction.transaction_uid,
                timeout_sec=timeout,
            )

            if _is_failed_transaction(transaction):
                module.fail_json(
                    msg=(
                        f"Secure Client push transaction {transaction.transaction_uid} "
                        f"failed with status: {transaction.cdo_transaction_status}"
                    ),
                    device_count=len(device_uids),
                    resolved_version=target_version,
                    transaction=transaction.to_dict(),
                )

        module.exit_json(
            changed=True,
            msg=(
                f"Secure Client version {target_version} pushed to "
                f"{len(device_uids)} device(s)."
                if wait_for_completion
                else f"Secure Client push of version {target_version} triggered on "
                f"{len(device_uids)} device(s)."
            ),
            device_count=len(device_uids),
            resolved_version=target_version,
            transaction=transaction.to_dict(),
        )

    except ApiException as e:
        error = SccApiError.from_exception(e)
        error_dict = error.to_dict()
        error_dict["msg"] = f"[while {stage}] {error_dict.get('msg', '')}"
        module.fail_json(**error_dict)
    except TimeoutError as e:
        module.fail_json(msg=f"[while {stage}] {e}")
    except ValueError as e:
        module.fail_json(msg=f"[while {stage}] {e}")
    except Exception as e:
        module.fail_json(msg=f"[while {stage}] Unexpected error: {e}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

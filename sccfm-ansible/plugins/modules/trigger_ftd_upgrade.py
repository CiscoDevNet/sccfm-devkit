from __future__ import annotations

from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import (
    ApiException,
    CdoTransaction,
    DevicePage,
    EntityType,
)

from sccfm_core import InventoryService, SccApiError
from sccfm_core.models.cdo_transaction_status import CdoTransactionStatus
from sccfm_core.services.inventory import (
    FtdUpgradeService,
    FtdUpgradeVersionService,
    resolve_upgrade_package_uid,
)
from sccfm_core.services.inventory.asa_upgrade_version_service import is_version_downgrade
from sccfm_core.services.transaction_service import TransactionService
from sccfm_core.types import ConfigLike

from ..module_utils.config import create_config

_FTD_ENTITY_TYPES = [
    EntityType.CDFMC_MANAGED_FTD,
    EntityType.FDM_MANAGED_FTD,
    EntityType.ONPREM_FMC_MANAGED_FTD,
]

DOCUMENTATION = r"""
---
module: trigger_ftd_upgrade
short_description: Trigger an FTD firmware upgrade
description:
  - Trigger a software upgrade on one or more FTD devices managed by
    SCC Firewall Manager.
  - Idempotent — if every eligible target device already runs the requested
    version, the module returns C(ok) (changed=False).
  - Devices that the upgrade API does not support (e.g. FDM-managed FTDs)
    are automatically skipped with a warning.
  - Validates that the software upgrade is not a downgrade.
  - Supports staging (download + readiness check only) via C(stage_upgrade).
options:
  query:
    description:
      - Lucene query to select FTD devices.
      - Mutually exclusive with C(uids).
      - The query is automatically combined with FTD device type filters.
    required: false
    type: str
  uids:
    description:
      - List of device UIDs to upgrade.
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
  software_version:
    description:
      - Target FTD software version (e.g. C(7.4.1)).
      - The module resolves the corresponding C(upgrade_package_uid) from
        the compatible versions list automatically.
    required: true
    type: str
  stage_upgrade:
    description:
      - Stage only — download image and run readiness checks without
        applying the upgrade.
    required: false
    type: bool
    default: false
  ignore_maintenance_window:
    description:
      - Allow upgrade outside the device maintenance window.
    required: false
    type: bool
    default: false
  upgrade_name:
    description:
      - Human-readable name to identify and track the upgrade run.
    required: false
    type: str
  wait:
    description:
      - Wait for the returned upgrade transaction to reach a terminal status.
      - When enabled, the module fails if the transaction ends in C(ERROR)
        or C(CANCELLED).
    required: false
    type: bool
    default: false
  timeout:
    description:
      - Maximum number of seconds to wait for the upgrade transaction when
        C(wait=true).
    required: false
    type: int
    default: 3600
  region:
    description: SCCFM region (int, us, eu, apj, aus, uae, in, or ci).
    required: false
    type: str
    env:
      - name: SCCFM_REGION
  api_token:
    description: API token for SCCFM.
    required: false
    type: str
    no_log: true
    env:
      - name: SCCFM_API_TOKEN
author:
  - Cisco SCCFM Team
"""

EXAMPLES = r"""
# Example 1: Upgrade specific FTD devices
- name: Trigger FTD upgrade
  cisco.sccfm.trigger_ftd_upgrade:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
    software_version: "7.4.1"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 2: Stage-only upgrade using a query
- name: Stage FTD upgrade for branch devices
  cisco.sccfm.trigger_ftd_upgrade:
    query: "name:branch-ftd-*"
    software_version: "7.4.1"
    stage_upgrade: true

# Example 3: Wait for the upgrade transaction to finish
- name: Trigger FTD upgrade and wait for completion
  cisco.sccfm.trigger_ftd_upgrade:
    uids:
      - "uid-1"
    software_version: "7.4.1"
    wait: true
    timeout: 3600
"""

RETURN = r"""
transaction:
  description: The triggered or completed transaction object for the upgrade.
  returned: success (changed=True)
  type: dict
device_count:
  description: Number of eligible devices included in the upgrade.
  returned: always
  type: int
skipped:
  description: >-
    Devices that were skipped because the upgrade API rejected them,
    keyed by device UID with the error message as value.
  returned: always
  type: dict
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
        "software_version": {"type": "str", "required": True},
        "stage_upgrade": {"type": "bool", "required": False, "default": False},
        "ignore_maintenance_window": {"type": "bool", "required": False, "default": False},
        "upgrade_name": {"type": "str", "required": False},
        "wait": {"type": "bool", "required": False, "default": False},
        "timeout": {"type": "int", "required": False, "default": 3600},
        "region": {"type": "str", "required": False},
        "api_token": {"type": "str", "required": False, "no_log": True},
    }


def resolve_device_uids_from_query(
    config: ConfigLike,
    query: str,
    limit: int,
    offset: int,
) -> list[str]:
    """Resolve device UIDs from a Lucene query."""
    inventory_service = InventoryService(config=config)
    type_filter = " OR ".join(f"deviceType:{t.value}" for t in _FTD_ENTITY_TYPES)
    page: DevicePage = inventory_service.get_devices(
        limit=limit,
        offset=offset,
        query=f"({query}) AND ({type_filter})",
    )
    return [device.uid for device in (page.items or [])]


def _all_devices_at_target(
    config: ConfigLike,
    device_uids: list[str],
    software_version: str,
) -> bool:
    """Return True if every device already runs the requested version."""
    inventory_service = InventoryService(config=config)
    for uid in device_uids:
        page: DevicePage = inventory_service.get_devices(limit=1, offset=0, query=f'uid:"{uid}"')
        if not page.items:
            return False
        device = page.items[0]
        if device.software_version != software_version:
            return False
    return True


def _validate_no_downgrade(
    config: ConfigLike,
    device_uids: list[str],
    software_version: str,
) -> str | None:
    """Return an error message if a software downgrade would occur, else None."""
    inventory_service = InventoryService(config=config)
    for uid in device_uids:
        page: DevicePage = inventory_service.get_devices(limit=1, offset=0, query=f'uid:"{uid}"')
        if not page.items:
            continue
        device = page.items[0]
        if device.software_version and is_version_downgrade(
            software_version, device.software_version
        ):
            return (
                f"Software version {software_version} is lower than "
                f"the current device software version {device.software_version}. "
                f"Downgrades are not supported."
            )
    return None


def _trigger_upgrade(
    config: ConfigLike,
    device_uids: list[str],
    upgrade_package_uid: str,
    stage_upgrade: bool,
    ignore_maintenance_window: bool,
    upgrade_name: str | None,
) -> CdoTransaction:
    """Trigger the upgrade via the appropriate single/multiple endpoint."""
    upgrade_service = FtdUpgradeService(config=config)
    if len(device_uids) == 1:
        return upgrade_service.upgrade_single(
            device_uid=device_uids[0],
            upgrade_package_uid=upgrade_package_uid,
            stage_upgrade=stage_upgrade,
            ignore_maintenance_window=ignore_maintenance_window,
            name=upgrade_name,
        )
    return upgrade_service.upgrade_multiple(
        device_uids=device_uids,
        upgrade_package_uid=upgrade_package_uid,
        stage_upgrade=stage_upgrade,
        ignore_maintenance_window=ignore_maintenance_window,
        name=upgrade_name,
    )


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

    config = create_config(module)

    software_version: str = module.params["software_version"]

    # Resolve device UIDs
    uids: list[str] | None = module.params.get("uids")
    query: str | None = module.params.get("query")

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

        # Resolve upgrade_package_uid and filter out incompatible devices
        version_service = FtdUpgradeVersionService(config=config)
        compat = version_service.get_compatible_versions(device_uids=device_uids)

        for uid, reason in compat.skipped.items():
            module.warn(f"Skipping device {uid}: {reason}")

        eligible_uids = [uid for uid in device_uids if uid in compat.per_device]

        if not eligible_uids:
            module.fail_json(
                msg="No eligible devices found. All devices were skipped by the upgrade API.",
                skipped=compat.skipped,
            )

        # Idempotency: skip if all eligible devices already at target version
        if _all_devices_at_target(config, eligible_uids, software_version):
            module.exit_json(
                changed=False,
                msg="All devices already at the requested version.",
                device_count=len(eligible_uids),
                skipped=compat.skipped,
            )

        # Downgrade validation
        downgrade_err = _validate_no_downgrade(config, eligible_uids, software_version)
        if downgrade_err:
            module.fail_json(msg=downgrade_err)

        # Resolve upgrade package UID from compatible versions
        upgrade_package_uid = resolve_upgrade_package_uid(compat.common_versions, software_version)
        if upgrade_package_uid is None:
            module.fail_json(
                msg=(
                    f"Software version {software_version} is not compatible "
                    f"with the selected device(s). "
                    f"Use list_ftd_compatible_versions to see available options."
                )
            )

        # Check mode
        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Would trigger upgrade on {len(eligible_uids)} device(s).",
                device_count=len(eligible_uids),
                skipped=compat.skipped,
                transaction={},
            )

        stage_upgrade: bool = module.params.get("stage_upgrade", False)
        ignore_maintenance_window: bool = module.params.get("ignore_maintenance_window", False)
        upgrade_name: str | None = module.params.get("upgrade_name")
        wait_for_completion: bool = module.params.get("wait", False)
        timeout: int = module.params.get("timeout", 3600)

        transaction = _trigger_upgrade(
            config=config,
            device_uids=eligible_uids,
            upgrade_package_uid=upgrade_package_uid,
            stage_upgrade=stage_upgrade,
            ignore_maintenance_window=ignore_maintenance_window,
            upgrade_name=upgrade_name,
        )

        if wait_for_completion:
            if transaction.transaction_uid is None:
                module.fail_json(msg="Transaction UID missing from upgrade response.")

            transaction = TransactionService(config=config).wait_for_transaction_to_finish(
                transaction_uid=transaction.transaction_uid,
                timeout_sec=timeout,
            )

            if _is_failed_transaction(transaction):
                module.fail_json(
                    msg=(
                        f"Upgrade transaction {transaction.transaction_uid} failed with status: "
                        f"{transaction.cdo_transaction_status}"
                    ),
                    device_count=len(eligible_uids),
                    skipped=compat.skipped,
                    transaction=transaction.to_dict(),
                )

        module.exit_json(
            changed=True,
            msg=(
                f"Upgrade completed on {len(eligible_uids)} device(s)."
                if wait_for_completion
                else f"Upgrade triggered on {len(eligible_uids)} device(s)."
            ),
            device_count=len(eligible_uids),
            skipped=compat.skipped,
            transaction=transaction.to_dict(),
        )

    except ApiException as e:
        error = SccApiError.from_exception(e)
        module.fail_json(**error.to_dict())
    except TimeoutError as e:
        module.fail_json(msg=str(e))
    except Exception as e:
        module.fail_json(msg=f"Unexpected error: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

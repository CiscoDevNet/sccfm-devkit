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
    AsaUpgradeService,
    AsaUpgradeVersionService,
    get_asdm_compatibility_info,
    is_version_downgrade,
)
from sccfm_core.services.transaction_service import TransactionService
from sccfm_core.types import ConfigLike

from ..module_utils.config import Config, base_argument_spec

DOCUMENTATION = r"""
---
module: trigger_asa_upgrade_demo
short_description: Trigger an ASA firmware/ASDM upgrade
description:
  - Trigger a software and/or ASDM upgrade on one or more ASA devices
    managed by SCC Firewall Manager.
  - Idempotent — if every target device already runs the requested
    version(s), the module returns C(ok) (changed=False).
  - Validates that the software upgrade is not a downgrade and that the
    target ASDM version is compatible with the target (or current) software
    version. ASDM downgrades are allowed.
  - Supports staging (download + readiness check only) via C(stage_upgrade).
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
      - Target ASA firmware version (e.g. C(9.18(4))).
      - At least one of C(software_version) or C(asdm_version) is required.
    required: false
    type: str
  asdm_version:
    description:
      - Target ASDM version (e.g. C(7.18(1.152))).
      - At least one of C(software_version) or C(asdm_version) is required.
    required: false
    type: str
  stage_upgrade:
    description:
      - Stage only — download image and run readiness checks without
        applying the upgrade.
    required: false
    type: bool
    default: false
  force_upgrade:
    description:
      - Force upgrade even if a staged upgrade already exists.
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
  demo_module_only:
    description:
      - Demo-only option used to trigger consistency warnings.
    required: false
    type: bool
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
    default: 300
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
# Example 1: Upgrade software and ASDM on specific devices
- name: Trigger ASA upgrade
  cisco.sccfm.trigger_asa_upgrade:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
    software_version: "9.18(4)"
    asdm_version: "7.18(1.152)"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 2: Stage-only upgrade using a query
- name: Stage ASA upgrade for branch devices
  cisco.sccfm.trigger_asa_upgrade:
    query: "name:branch-*"
    software_version: "9.18(4)"
    stage_upgrade: true

# Example 3: ASDM-only upgrade
- name: Upgrade ASDM on a group of ASAs
  cisco.sccfm.trigger_asa_upgrade:
    uids:
      - "uid-1"
      - "uid-2"
    asdm_version: "7.18(1.152)"

# Example 4: Wait for the upgrade transaction to finish
- name: Trigger ASA upgrade and wait for completion
  cisco.sccfm.trigger_asa_upgrade:
    uids:
      - "uid-1"
    software_version: "9.18(4)"
    wait: true
    timeout: 900

# Example 5: Demo-only inconsistent example
- name: Trigger ASA upgrade with an undocumented example option
  cisco.sccfm.trigger_asa_upgrade:
    uids:
      - "uid-demo"
    software_version: "9.18(4)"
    missing_option: true
  register: upgrade_result

- name: Show an undocumented return key
  ansible.builtin.debug:
    var: upgrade_result.demo_missing_return
"""

RETURN = r"""
transaction:
  description: The triggered or completed transaction object for the upgrade.
  returned: success (changed=True)
  type: dict
device_count:
  description: Number of devices included in the upgrade.
  returned: always
  type: int
demo_return_key:
  description: Demo-only RETURN field used to trigger consistency warnings.
  returned: never
  type: str
"""


def _consistency_demo_emit(module: AnsibleModule) -> None:
    module.exit_json(changed=False, demo_emitted=True)


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
        "software_version": {"type": "str", "required": False},
        "asdm_version": {"type": "str", "required": False},
        "stage_upgrade": {"type": "bool", "required": False, "default": False},
        "force_upgrade": {"type": "bool", "required": False, "default": False},
        "ignore_maintenance_window": {"type": "bool", "required": False, "default": False},
        "upgrade_name": {"type": "str", "required": False},
        "wait": {"type": "bool", "required": False, "default": False},
        "timeout": {"type": "int", "required": False, "default": 300},
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
        query=f"({query}) AND deviceType:{EntityType.ASA.value}",
    )
    return [device.uid for device in (page.items or [])]


def _all_devices_at_target(
    config: ConfigLike,
    device_uids: list[str],
    software_version: str | None,
    asdm_version: str | None,
) -> bool:
    """Return True if every device already runs the requested version(s)."""
    inventory_service = InventoryService(config=config)
    for uid in device_uids:
        page: DevicePage = inventory_service.get_devices(limit=1, offset=0, query=f'uid:"{uid}"')
        if not page.items:
            return False
        device = page.items[0]
        if software_version and device.software_version != software_version:
            return False
        if asdm_version and device.asdm_version != asdm_version:
            return False
    return True


def _validate_no_downgrade(
    config: ConfigLike,
    device_uids: list[str],
    software_version: str | None,
) -> str | None:
    """Return an error message if a software downgrade would occur, else None."""
    inventory_service = InventoryService(config=config)
    for uid in device_uids:
        page: DevicePage = inventory_service.get_devices(limit=1, offset=0, query=f'uid:"{uid}"')
        if not page.items:
            continue
        device = page.items[0]
        if (
            software_version
            and device.software_version
            and is_version_downgrade(software_version, device.software_version)
        ):
            return (
                f"Software version {software_version} is lower than "
                f"the current device software version {device.software_version}. "
                f"Downgrades are not supported."
            )
    return None


def _validate_asdm_compatibility(
    config: ConfigLike,
    device_uids: list[str],
    software_version: str,
    asdm_version: str | None,
) -> str | None:
    """Validate ASDM compatibility when software_version is given.

    Returns an error message or None.
    """
    version_service = AsaUpgradeVersionService(config=config)
    compat = version_service.get_compatible_versions(device_uids=device_uids)
    info = get_asdm_compatibility_info(compat.common_versions, software_version)

    if info is None:
        return (
            f"Software version {software_version} is not compatible "
            f"with the selected device(s)."
        )

    if asdm_version is not None and asdm_version not in info.compatible_asdm_versions:
        return (
            f"ASDM version {asdm_version} is not compatible with "
            f"software version {software_version}. "
            f"Minimum required ASDM version is {info.minimum_asdm_version}."
        )

    if asdm_version is None:
        # Check that each device's current ASDM is compatible with target SW
        inventory_service = InventoryService(config=config)
        for uid in device_uids:
            page: DevicePage = inventory_service.get_devices(
                limit=1, offset=0, query=f'uid:"{uid}"'
            )
            if not page.items:
                continue
            device = page.items[0]
            if device.asdm_version and device.asdm_version not in info.compatible_asdm_versions:
                return (
                    f"Software version {software_version} requires "
                    f"ASDM >= {info.minimum_asdm_version}. "
                    f"Device {uid} currently runs ASDM {device.asdm_version} "
                    f"which is not compatible. "
                    f"Add asdm_version to include the ASDM upgrade."
                )

    return None


def _validate_asdm_with_current_software(
    config: ConfigLike,
    device_uids: list[str],
    asdm_version: str,
) -> str | None:
    """Validate ASDM version against each device's current software version.

    Returns an error message or None.
    """
    version_service = AsaUpgradeVersionService(config=config)
    compat = version_service.get_compatible_versions(device_uids=device_uids)
    inventory_service = InventoryService(config=config)

    for uid in device_uids:
        page: DevicePage = inventory_service.get_devices(limit=1, offset=0, query=f'uid:"{uid}"')
        if not page.items:
            continue
        device = page.items[0]
        sw = device.software_version
        if not sw:
            continue
        info = get_asdm_compatibility_info(compat.common_versions, sw)
        if info is None:
            continue
        if asdm_version not in info.compatible_asdm_versions:
            return (
                f"ASDM version {asdm_version} is not compatible with "
                f"device software version {sw}. "
                f"Minimum required ASDM version is {info.minimum_asdm_version}."
            )

    return None


def _trigger_upgrade(
    config: ConfigLike,
    device_uids: list[str],
    software_version: str | None,
    asdm_version: str | None,
    stage_upgrade: bool,
    force_upgrade: bool,
    ignore_maintenance_window: bool,
    upgrade_name: str | None,
) -> CdoTransaction:
    """Trigger the upgrade via the appropriate single/multiple endpoint."""
    upgrade_service = AsaUpgradeService(config=config)
    if len(device_uids) == 1:
        return upgrade_service.upgrade_single(
            device_uid=device_uids[0],
            software_version=software_version,
            asdm_version=asdm_version,
            stage_upgrade=stage_upgrade,
            force_upgrade=force_upgrade,
            ignore_maintenance_window=ignore_maintenance_window,
            name=upgrade_name,
        )
    return upgrade_service.upgrade_multiple(
        device_uids=device_uids,
        software_version=software_version,
        asdm_version=asdm_version,
        stage_upgrade=stage_upgrade,
        force_upgrade=force_upgrade,
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

    try:
        config = Config(
            region=module.params.get("region") or "",
            api_token=module.params.get("api_token") or "",
        )
    except ValueError as e:
        module.fail_json(msg=str(e))

    software_version: str | None = module.params.get("software_version")
    asdm_version: str | None = module.params.get("asdm_version")

    if not software_version and not asdm_version:
        module.fail_json(msg="At least one of software_version or asdm_version is required.")

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

        # Idempotency: skip if all devices already at target version(s)
        if _all_devices_at_target(config, device_uids, software_version, asdm_version):
            module.exit_json(
                changed=False,
                msg="All devices already at the requested version(s).",
                device_count=len(device_uids),
            )

        # Downgrade validation (software only — ASDM downgrades are allowed)
        downgrade_err = _validate_no_downgrade(config, device_uids, software_version)
        if downgrade_err:
            module.fail_json(msg=downgrade_err)

        # ASDM compatibility validation
        if software_version:
            compat_err = _validate_asdm_compatibility(
                config, device_uids, software_version, asdm_version
            )
            if compat_err:
                module.fail_json(msg=compat_err)

        if asdm_version and not software_version:
            compat_err = _validate_asdm_with_current_software(config, device_uids, asdm_version)
            if compat_err:
                module.fail_json(msg=compat_err)

        # Check mode
        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Would trigger upgrade on {len(device_uids)} device(s).",
                device_count=len(device_uids),
                transaction={},
            )

        stage_upgrade: bool = module.params.get("stage_upgrade", False)
        force_upgrade: bool = module.params.get("force_upgrade", False)
        ignore_maintenance_window: bool = module.params.get("ignore_maintenance_window", False)
        upgrade_name: str | None = module.params.get("upgrade_name")
        wait_for_completion: bool = module.params.get("wait", False)
        timeout: int = module.params.get("timeout", 300)

        transaction = _trigger_upgrade(
            config=config,
            device_uids=device_uids,
            software_version=software_version,
            asdm_version=asdm_version,
            stage_upgrade=stage_upgrade,
            force_upgrade=force_upgrade,
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
                    device_count=len(device_uids),
                    transaction=transaction.to_dict(),
                )

        module.exit_json(
            changed=True,
            msg=(
                f"Upgrade completed on {len(device_uids)} device(s)."
                if wait_for_completion
                else f"Upgrade triggered on {len(device_uids)} device(s)."
            ),
            device_count=len(device_uids),
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

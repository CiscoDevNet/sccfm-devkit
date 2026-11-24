# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

DOCUMENTATION = r"""
---
module: sync_asa_device_config
short_description: Trigger CDO to re-read an ASA's live running-config on demand
description:
  - Triggers an on-demand read of one or more ASA devices' live
    running-config into CDO - the API equivalent of the CDO UI's
    "Sync"/"accept out-of-band changes" action on a device's page.
  - Needed after pushing config directly via raw CLI (e.g.
    C(cisco.sccfm.execute_asa_cli)) before CDO's own cached device model,
    device-role auto-detection (for example C(ASA_RA_VPN_HEADEND), required
    by the Secure Client Management catalog APIs), or any UI picker that
    reads off that cached model will reflect the change. Without this, the
    tenant's background out-of-band conflict-detection poll would
    eventually pick it up instead - by default every 6 hours.
  - This always triggers a read (not idempotent in the usual sense) - there
    is no cheap way to tell in advance whether the device's cached config
    is already current, so C(changed) is always C(True) on success.
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
      - List of device UIDs to sync.
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
  wait:
    description:
      - Wait for every triggered read transaction to reach a terminal status.
      - When enabled, the module fails if any transaction ends in C(ERROR)
        or C(CANCELLED).
    required: false
    type: bool
    default: false
  timeout:
    description:
      - Maximum number of seconds to wait for each read transaction when
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
# Example 1: Sync specific devices and wait for completion
- name: Sync ASA config after a CLI push
  cisco.sccfm.sync_asa_device_config:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
    wait: true
    timeout: 600

# Example 2: Sync devices matching a query, fire-and-forget
- name: Sync branch ASAs
  cisco.sccfm.sync_asa_device_config:
    query: "name:branch-*"
"""

RETURN = r"""
results:
  description: Per-device sync result.
  returned: success
  type: list
  elements: dict
  contains:
    device_uid:
      description: The UID of the device.
      type: str
    transaction:
      description: The triggered or completed transaction object for the read.
      type: dict
device_count:
  description: Number of devices synced.
  returned: always
  type: int
"""


from typing import Any, cast

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException, CdoTransaction, DevicePage

    from cisco_sccfm_core import ASA_DEVICE_TYPE_FILTER, InventoryService, SccApiError
    from cisco_sccfm_core.constants import DEFAULT_TRANSACTION_TIMEOUT_SEC
    from cisco_sccfm_core.models.cdo_transaction_status import CdoTransactionStatus
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

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Would sync {len(device_uids)} device(s).",
                device_count=len(device_uids),
                results=[],
            )

        wait_for_completion: bool = module.params.get("wait", False)
        timeout: int = module.params.get("timeout", DEFAULT_TRANSACTION_TIMEOUT_SEC)

        inventory_service = InventoryService(config=config)
        results: list[dict[str, Any]] = []
        for device_uid in device_uids:
            transaction = inventory_service.read_asa_device_configuration(
                device_uid=device_uid
            )

            if wait_for_completion:
                if transaction.transaction_uid is None:
                    module.fail_json(
                        msg=f"Transaction UID missing from sync response for {device_uid}."
                    )

                transaction = TransactionService(config=config).wait_for_transaction_to_finish(
                    transaction_uid=transaction.transaction_uid,
                    timeout_sec=timeout,
                )

                if _is_failed_transaction(transaction):
                    module.fail_json(
                        msg=(
                            f"Sync transaction {transaction.transaction_uid} for device "
                            f"{device_uid} failed with status: "
                            f"{transaction.cdo_transaction_status}"
                        ),
                        device_count=len(device_uids),
                        results=results,
                    )

            results.append({"device_uid": device_uid, "transaction": transaction.to_dict()})

        module.exit_json(
            changed=True,
            msg=(
                f"Synced {len(device_uids)} device(s)."
                if wait_for_completion
                else f"Sync triggered on {len(device_uids)} device(s)."
            ),
            device_count=len(device_uids),
            results=results,
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

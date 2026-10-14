# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

DOCUMENTATION = r"""
---
module: read_asa_config
short_description: Read ASA running configuration into SCC Firewall Manager
description:
  - Read the running configuration of one or more ASA devices into SCC Firewall
    Manager.
  - Use after changing a device outside SCC Firewall Manager, for example with
    M(cisco.sccfm.execute_asa_cli). SCC Firewall Manager does not re-read the
    device on its own, so access groups, rules, and objects added that way do
    not appear until a read.
  - The read replaces SCC Firewall Manager's copy of the configuration, so
    changes staged there but not yet deployed can be lost.
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
      - List of device UIDs to read.
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
      - Wait for the read transaction to reach a terminal status.
      - When enabled, the module fails if the transaction ends in C(ERROR)
        or C(CANCELLED).
    required: false
    type: bool
    default: false
  timeout:
    description:
      - Maximum number of seconds to wait for the read transaction when
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
# Example 1: Push config with the CLI, then read it back into SCC Firewall Manager
- name: Create an ACL on the branch ASAs
  cisco.sccfm.execute_asa_cli:
    query: "name:branch-*"
    commands:
      - "access-list branch-acl extended permit ip any any"
  register: cli_result

- name: Read the new configuration into SCC Firewall Manager
  cisco.sccfm.read_asa_config:
    uids: "{{ cli_result.results | map(attribute='device_uid') | list }}"
    wait: true
    timeout: 300

# Example 2: Shared profile via module_defaults, without waiting for the read
- name: Read ASA configuration
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Start a configuration read
      cisco.sccfm.read_asa_config:
        uids:
          - "12345678-1234-1234-1234-123456789abc"
"""

RETURN = r"""
transaction:
  description: The started or completed transaction object for the read.
  returned: success (changed=True)
  type: dict
device_count:
  description: Number of devices included in the read.
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
    from cisco_sccfm_core.services.inventory import AsaConfigReadService
    from cisco_sccfm_core.services.transaction_service import TransactionService
    from cisco_sccfm_core.types import ConfigLike
except ImportError as exc:
    record_import_error(exc)
    ApiException = RuntimeError
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


def _wait_for_read(
    module: AnsibleModule, config: ConfigLike, transaction: CdoTransaction, device_count: int
) -> CdoTransaction:
    if transaction.transaction_uid is None:
        module.fail_json(msg="Transaction UID missing from configuration read response.")
    transaction = TransactionService(config=config).wait_for_transaction_to_finish(
        transaction_uid=cast(str, transaction.transaction_uid),
        timeout_sec=module.params["timeout"],
    )
    if _is_failed_transaction(transaction):
        module.fail_json(
            msg=(
                f"Configuration read transaction {transaction.transaction_uid} failed with "
                f"status: {transaction.cdo_transaction_status}"
            ),
            device_count=device_count,
            transaction=transaction.to_dict(),
        )
    return transaction


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
    wait_for_completion: bool = module.params["wait"]

    try:
        device_uids = uids or resolve_device_uids_from_query(
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
                msg=f"Would read configuration from {len(device_uids)} device(s).",
                device_count=len(device_uids),
                transaction={},
            )

        transaction = AsaConfigReadService(config=config).read_configuration(
            device_uids=device_uids
        )
        if wait_for_completion:
            transaction = _wait_for_read(module, config, transaction, len(device_uids))

        module.exit_json(
            changed=True,
            msg=(
                f"Configuration read completed for {len(device_uids)} device(s)."
                if wait_for_completion
                else f"Configuration read started for {len(device_uids)} device(s)."
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

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
from sccfm_core.services.inventory import FtdDeployService
from sccfm_core.types import ConfigLike

from ..module_utils.config import Config, base_argument_spec

DOCUMENTATION = r"""
---
module: deploy_cdfmc_ftd
short_description: Deploy changes to cdFMC-managed FTD devices
description:
  - Deploy pending configuration changes to one or more cdFMC-managed FTD
    devices via SCC Firewall Manager.
  - Supports deploying to a single device or up to 50 devices in parallel.
options:
  query:
    description:
      - Lucene query to select cdFMC-managed FTD devices.
      - Mutually exclusive with C(uids).
      - The query is automatically combined with C(deviceType:CDFMC_MANAGED_FTD).
    required: false
    type: str
  uids:
    description:
      - List of device UIDs to deploy.
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
  deployment_notes:
    description:
      - Notes for the deployment.
    required: false
    type: str
  description:
    description:
      - Human-readable description for the deployment.
    required: false
    type: str
  ignore_warnings:
    description:
      - Ignore warnings from pre-validation and proceed with deployment.
    required: false
    type: bool
    default: false
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
# Example 1: Deploy changes to specific FTD devices
- name: Deploy FTD changes
  cisco.sccfm.deploy_cdfmc_ftd:
    uids:
      - "12345678-1234-1234-1234-123456789abc"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"

# Example 2: Deploy with notes
- name: Deploy FTD changes with deployment notes
  cisco.sccfm.deploy_cdfmc_ftd:
    uids:
      - "uid-1"
      - "uid-2"
    deployment_notes: "Ticket-123: firewall policy update"
    description: "Deploy updated access rules"

# Example 3: Deploy using a query
- name: Deploy to all branch FTD devices
  cisco.sccfm.deploy_cdfmc_ftd:
    query: "name:branch-*"
    ignore_warnings: true
"""

RETURN = r"""
transaction:
  description: The transaction object tracking the async deployment.
  returned: success (changed=True)
  type: dict
device_count:
  description: Number of devices included in the deployment.
  returned: always
  type: int
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "query": {"type": "str", "required": False},
        "uids": {"type": "list", "elements": "str", "required": False},
        "limit": {"type": "int", "required": False, "default": 50},
        "offset": {"type": "int", "required": False, "default": 0},
        "deployment_notes": {"type": "str", "required": False},
        "description": {"type": "str", "required": False},
        "ignore_warnings": {"type": "bool", "required": False, "default": False},
        **base_argument_spec(),
    }


def resolve_device_uids_from_query(
    config: ConfigLike,
    query: str,
    limit: int,
    offset: int,
) -> list[str]:
    inventory_service = InventoryService(config=config)
    page: DevicePage = inventory_service.get_devices(
        limit=limit,
        offset=offset,
        query=f"({query}) AND deviceType:{EntityType.CDFMC_MANAGED_FTD.value}",
    )
    return [device.uid for device in (page.items or [])]


def _trigger_deploy(
    config: ConfigLike,
    device_uids: list[str],
    deployment_notes: str | None,
    description: str | None,
    ignore_warnings: bool,
) -> CdoTransaction:
    deploy_service = FtdDeployService(config=config)
    if len(device_uids) == 1:
        return deploy_service.deploy_single(
            device_uid=device_uids[0],
            deployment_notes=deployment_notes,
            description=description,
            ignore_warnings=ignore_warnings,
        )
    return deploy_service.deploy_multiple(
        device_uids=device_uids,
        deployment_notes=deployment_notes,
        description=description,
        ignore_warnings=ignore_warnings,
    )


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

        # Check mode
        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Would deploy to {len(device_uids)} device(s).",
                device_count=len(device_uids),
                transaction={},
            )

        deployment_notes: str | None = module.params.get("deployment_notes")
        description: str | None = module.params.get("description")
        ignore_warnings: bool = module.params.get("ignore_warnings", False)

        transaction = _trigger_deploy(
            config=config,
            device_uids=device_uids,
            deployment_notes=deployment_notes,
            description=description,
            ignore_warnings=ignore_warnings,
        )

        module.exit_json(
            changed=True,
            msg=f"Deploy triggered on {len(device_uids)} device(s).",
            device_count=len(device_uids),
            transaction=transaction.to_dict(),
        )

    except ApiException as e:
        error = SccApiError.from_exception(e)
        module.fail_json(**error.to_dict())
    except Exception as e:
        module.fail_json(msg=f"Unexpected error: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

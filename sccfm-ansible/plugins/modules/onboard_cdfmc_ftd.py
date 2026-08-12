# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0
# flake8: noqa: E402
# isort: skip_file

from __future__ import annotations

DOCUMENTATION = r"""
---
module: onboard_cdfmc_ftd
short_description: Onboard a cdFMC-managed FTD device (non-ZTP) to SCC Firewall Manager
description:
  - Onboard a cdFMC-managed FTD device using the manual (non-ZTP) registration flow.
  - After the device is created, the module returns a CLI key that must be pasted into
    the FTD device's CLI to complete registration with the cdFMC.
options:
  name:
    description: Human-readable name for the FTD device.
    required: true
    type: str
  fmc_access_policy_uid:
    description: UUID of the FMC access policy to apply to this device.
    required: true
    type: str
  licenses:
    description:
      - List of licenses to apply to the device.
      - At least one license is required.
    required: true
    type: list
    elements: str
    choices: ["BASE", "CARRIER", "THREAT", "MALWARE", "URLFilter"]
  virtual:
    description:
      - Indicate whether the FTD is a virtual device.
      - When true, C(performance_tier) is required.
    required: false
    type: bool
    default: false
  performance_tier:
    description:
      - Performance tier of the FTDv.
      - Required when C(virtual) is true.
    required: false
    type: str
    choices: ["FTDv5", "FTDv10", "FTDv20", "FTDv30", "FTDv50", "FTDv100", "FTDv"]
  grouped_labels:
    description: Mapping of grouped labels to assign to the device.
    required: false
    type: dict
  ungrouped_labels:
    description: List of free-form labels to assign to the device.
    required: false
    type: list
    elements: str
  region:
    description: SCCFM region (int, us, eu, apj, au, uae, in, or ci).
    required: false
    type: str
  api_token:
    description: API token for SCCFM.
    required: false
    type: str
author:
  - huides00 (@huides00)
  - Scoombe (@Scoombe)
  - afercal (@afercal)
"""

EXAMPLES = r"""
# Example 1: Onboard a physical cdFMC-managed FTD
- name: Onboard FTD device
  cisco.sccfm.onboard_cdfmc_ftd:
    name: "My FTD"
    fmc_access_policy_uid: "your-access-policy-uid"
    licenses:
      - BASE
    region: "{{ lookup('env', 'SCCFM_REGION') }}"
    api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"

# Example 2: Onboard a virtual FTD with multiple licenses
- name: Onboard virtual FTD
  cisco.sccfm.onboard_cdfmc_ftd:
    name: "My vFTD"
    fmc_access_policy_uid: "your-access-policy-uid"
    licenses:
      - BASE
      - CARRIER
    virtual: true
    performance_tier: "FTDv5"

# Example 3: Onboard with labels
- name: Onboard FTD with labels
  cisco.sccfm.onboard_cdfmc_ftd:
    name: "Branch FTD"
    fmc_access_policy_uid: "your-access-policy-uid"
    licenses:
      - BASE
    ungrouped_labels:
      - ra-vpn-headend
    grouped_labels:
      environment:
        - prod

# Example 4: Using module_defaults (recommended)
- name: Onboard cdFMC-managed FTD
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ lookup('env', 'SCCFM_REGION') }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  tasks:
    - name: Onboard branch FTD
      cisco.sccfm.onboard_cdfmc_ftd:
        name: "Branch FTD"
        fmc_access_policy_uid: "your-access-policy-uid"
        licenses:
          - BASE
"""

RETURN = r"""
cli_key:
  description:
    - The CLI key to paste into the FTD device's CLI to register it with the cdFMC.
    - Paste this value into the FTD CLI once to complete onboarding.
    - Can be passed directly to a subsequent SSH task.
  returned: success (changed=True)
  type: str
device:
  description: The newly onboarded cdFMC-managed FTD device.
  returned: success
  type: dict
"""


from typing import Optional

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.config import Config, base_argument_spec, create_config
from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import (
        ApiException,
        Device,
        DevicePage,
        EntityType,
        FtdCreateOrUpdateInput,
        Labels,
    )

    from cisco_sccfm_core import InventoryService, SccApiError
    from cisco_sccfm_core.services.inventory import FtdOnboardService
    from cisco_sccfm_core.types import ConfigLike
except ImportError as exc:
    record_import_error(exc)


_VALID_LICENSES = ["BASE", "CARRIER", "THREAT", "MALWARE", "URLFilter"]
_VALID_PERFORMANCE_TIERS = ["FTDv5", "FTDv10", "FTDv20", "FTDv30", "FTDv50", "FTDv100", "FTDv"]


def build_argument_spec() -> dict:
    return {
        "name": {"type": "str", "required": True},
        "fmc_access_policy_uid": {"type": "str", "required": True},
        "licenses": {
            "type": "list",
            "elements": "str",
            "required": True,
            "choices": _VALID_LICENSES,
        },
        "virtual": {"type": "bool", "required": False, "default": False},
        "performance_tier": {"type": "str", "required": False, "choices": _VALID_PERFORMANCE_TIERS},
        "grouped_labels": {"type": "dict", "required": False},
        "ungrouped_labels": {"type": "list", "elements": "str", "required": False},
        **base_argument_spec(),
    }


def _check_name_exists(config: ConfigLike, name: str) -> bool:
    inventory_service = InventoryService(config=config)
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    page: DevicePage = inventory_service.get_devices(
        limit=1,
        offset=0,
        query=f'deviceType:{EntityType.CDFMC_MANAGED_FTD.value} AND name:"{escaped}"',
    )
    return page.count is not None and page.count > 0


def _build_ftd_input(
    name: str,
    fmc_access_policy_uid: str,
    licenses: list[str],
    virtual: bool,
    performance_tier: Optional[str],
    grouped_labels: Optional[dict],
    ungrouped_labels: Optional[list[str]],
) -> FtdCreateOrUpdateInput:
    labels = None
    if grouped_labels or ungrouped_labels:
        labels = Labels(
            groupedLabels=grouped_labels,
            ungroupedLabels=ungrouped_labels,
        )

    return FtdCreateOrUpdateInput(
        deviceType="CDFMC_MANAGED_FTD",
        fmcAccessPolicyUid=fmc_access_policy_uid,
        name=name,
        licenses=licenses,
        virtual=virtual if virtual else None,
        performanceTier=performance_tier,
        labels=labels,
    )


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config: Config = create_config(module)
    name: str = module.params["name"]
    fmc_access_policy_uid: str = module.params["fmc_access_policy_uid"]
    licenses: list[str] = module.params["licenses"]
    virtual: bool = module.params.get("virtual", False)
    performance_tier: Optional[str] = module.params.get("performance_tier")
    grouped_labels: Optional[dict] = module.params.get("grouped_labels")
    ungrouped_labels: Optional[list[str]] = module.params.get("ungrouped_labels")

    if not licenses:
        module.fail_json(msg="At least one license is required.")
        return

    invalid_licenses = [lic for lic in licenses if lic not in _VALID_LICENSES]
    if invalid_licenses:
        module.fail_json(
            msg=f"Invalid license(s): {invalid_licenses}. Must be one of: {_VALID_LICENSES}."
        )
        return

    if virtual and not performance_tier:
        module.fail_json(msg="performance_tier is required when virtual is true.")
        return

    try:
        if _check_name_exists(config, name):
            module.fail_json(msg=f"cdFMC-managed FTD device with name '{name}' already exists.")
            return

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Would onboard cdFMC-managed FTD device '{name}'.",
                cli_key=None,
                device={},
            )
            return

        ftd_input = _build_ftd_input(
            name=name,
            fmc_access_policy_uid=fmc_access_policy_uid,
            licenses=licenses,
            virtual=virtual,
            performance_tier=performance_tier,
            grouped_labels=grouped_labels,
            ungrouped_labels=ungrouped_labels,
        )

        ftd_onboard_service = FtdOnboardService(config=config)
        device: Device = ftd_onboard_service.onboard_ftd(ftd_create_or_update_input=ftd_input)

        cli_key = device.cd_fmc_info.cli_key if device.cd_fmc_info else None

        module.exit_json(
            changed=True,
            msg=f"cdFMC-managed FTD device '{name}' onboarded successfully.",
            cli_key=cli_key,
            device=device.to_dict(),
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

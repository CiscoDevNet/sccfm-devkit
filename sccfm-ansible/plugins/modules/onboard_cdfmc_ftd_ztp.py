# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Optional

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import (
        ApiException,
        Device,
        DevicePage,
        EntityType,
        ZtpOnboardingInput,
    )

    from cisco_sccfm_core import InventoryService, SccApiError
    from cisco_sccfm_core.services.inventory import FtdZtpOnboardService
    from cisco_sccfm_core.types import ConfigLike
except ImportError as exc:
    record_import_error(exc)
    ApiException = NotFoundError = FtdConfigureManagerError = RuntimeError


from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: onboard_cdfmc_ftd_ztp
short_description: Onboard a cdFMC-managed FTD device using Zero-Touch Provisioning
description:
  - Onboard a cdFMC-managed FTD device via Zero-Touch Provisioning (ZTP).
  - The device registers automatically when it is plugged in and connects to the Internet.
  - Applies to 1xxx/2xxx/3xxx series physical FTD devices.
  - This module is idempotent - if a device with the same name and serial number is already
    onboarded, it returns C(changed=False) without error.
  - If the name is already taken by a device with a different serial number, the module fails
    with a clear error message.
  - >
    Note: the inventory API does not support searching by serial number, so a device onboarded
    under a different name with the same serial cannot be detected at this stage. The API will
    return an error in that case.
options:
  name:
    description: Human-readable name for the FTD device.
    required: true
    type: str
  serial_number:
    description: Serial number of the physical FTD device.
    required: true
    type: str
  licenses:
    description:
      - List of licenses to apply to the device. At least one is required.
    required: true
    type: list
    elements: str
    choices: ["BASE", "CARRIER", "THREAT", "MALWARE", "URLFilter"]
  fmc_access_policy_uid:
    description:
      - UUID of the FMC access policy to apply to this device.
    required: true
    type: str
  admin_password:
    description:
      - Initial provisioning password for the FTD device.
      - Required if a password has not already been set on the device.
    required: false
    type: str
    no_log: true
  device_group_uid:
    description: UUID of the device group the device will join after registration.
    required: false
    type: str
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
  - Cisco SCCFM Team
"""

EXAMPLES = r"""
# Example 1: Onboard a physical FTD via ZTP
- name: Onboard FTD via ZTP
  cisco.sccfm.onboard_cdfmc_ftd_ztp:
    name: "Branch FTD"
    serial_number: "FTD1234567890"
    licenses:
      - BASE
    fmc_access_policy_uid: "00000000-0000-0000-0000-000000000000"
    profile: default

# Example 2: Onboard with initial password and device group
- name: Onboard FTD via ZTP with password
  cisco.sccfm.onboard_cdfmc_ftd_ztp:
    name: "Branch FTD"
    serial_number: "FTD1234567890"
    licenses:
      - BASE
      - CARRIER
    fmc_access_policy_uid: "00000000-0000-0000-0000-000000000000"
    admin_password: "{{ ftd_admin_password }}"
    device_group_uid: "abcd1234-0000-0000-0000-000000000001"

# Example 3: Using module_defaults (recommended)
- name: Onboard cdFMC-managed FTD with ZTP
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Onboard branch FTD through ZTP
      cisco.sccfm.onboard_cdfmc_ftd_ztp:
        name: "Branch FTD"
        serial_number: "FTD1234567890"
        licenses:
          - BASE
        fmc_access_policy_uid: "00000000-0000-0000-0000-000000000000"
"""

RETURN = r"""
device_uid:
  description:
    - The UID of the onboarded FTD device in SCC Firewall Manager.
    - C(None) when the module runs in check mode or the device already existed (C(changed=False)).
  returned: always
  type: str
"""

_VALID_LICENSES = ["BASE", "CARRIER", "THREAT", "MALWARE", "URLFilter"]


def build_argument_spec() -> dict:
    return {
        "name": {"type": "str", "required": True},
        "serial_number": {"type": "str", "required": True},
        "licenses": {"type": "list", "elements": "str", "required": True},
        "fmc_access_policy_uid": {"type": "str", "required": True},
        "admin_password": {"type": "str", "required": False, "no_log": True},
        "device_group_uid": {"type": "str", "required": False},
        **base_argument_spec(),
    }


def _query_by_name(config: ConfigLike, name: str) -> DevicePage:
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return InventoryService(config=config).get_devices(
        limit=1,
        offset=0,
        query=f'deviceType:{EntityType.CDFMC_MANAGED_FTD.value} AND name:"{escaped}"',
    )


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config: Config = create_config(module)
    name: str = module.params["name"]
    serial_number: str = module.params["serial_number"]
    licenses: list[str] = module.params["licenses"]
    fmc_access_policy_uid: str = module.params["fmc_access_policy_uid"]
    admin_password: Optional[str] = module.params.get("admin_password")
    device_group_uid: Optional[str] = module.params.get("device_group_uid")

    if not licenses:
        module.fail_json(msg="At least one license is required.")
        return

    invalid_licenses = [lic for lic in licenses if lic not in _VALID_LICENSES]
    if invalid_licenses:
        module.fail_json(
            msg=f"Invalid license(s): {invalid_licenses}. Must be one of: {_VALID_LICENSES}."
        )
        return

    try:
        name_page = _query_by_name(config, name)
        name_match: Optional[Device] = (
            name_page.items[0] if name_page.count and name_page.items else None
        )

        if name_match is not None:
            # Idempotency: same device (name + serial match) already onboarded
            if name_match.serial == serial_number:
                module.exit_json(
                    changed=False,
                    msg=f"cdFMC-managed FTD device '{name}' with serial '{serial_number}' "
                    f"is already onboarded.",
                    device_uid=name_match.uid,
                )
                return
            # Name taken by a device with a different serial
            module.fail_json(
                msg=f"A cdFMC-managed FTD device named '{name}' already exists with a different "
                f"serial number (uid: {name_match.uid})."
            )
            return

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Would onboard cdFMC-managed FTD device '{name}' via ZTP.",
                device_uid=None,
            )
            return

        ztp_input = ZtpOnboardingInput(
            name=name,
            serialNumber=serial_number,
            licenses=licenses,
            fmcAccessPolicyUid=fmc_access_policy_uid,
            adminPassword=admin_password,
            deviceGroupUid=device_group_uid,
        )

        ztp_service = FtdZtpOnboardService(config=config)
        device: Device = ztp_service.onboard_ftd_ztp(ztp_onboarding_input=ztp_input)

        module.exit_json(
            changed=True,
            msg=f"cdFMC-managed FTD device '{name}' onboarded via ZTP successfully.",
            device_uid=device.uid,
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

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Optional

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import (
    ApiException,
    AsaCreateOrUpdateInput,
    ConnectorType,
    Device,
    DevicePage,
    Labels,
)

from cisco_sccfm_core import ASA_DEVICE_TYPE_FILTER, InventoryService, SccApiError
from cisco_sccfm_core.services.inventory import AsaOnboardService
from cisco_sccfm_core.types import ConfigLike

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: onboard_asa
short_description: Onboard an ASA to your SCC Firewall Manager tenant
description:
  - Onboard an ASA device to your SCC Firewall Manager tenant
options:
  name:
    description: Human-readable name for the ASA device.
    required: true
    type: str
  device_address:
    description: Device address in the form host:port.
    required: true
    type: str
  username:
    description: Username used to authenticate with the device.
    required: true
    type: str
  password:
    description: Password used to authenticate with the device.
    required: true
    type: str
    no_log: true
  connector_type:
    description: Connector type used to communicate with the device.
    required: true
    type: str
    choices: ["SDC", "CDG"]
  connector_name:
    description: Name of the Secure Device Connector (SDC) to use (required when
      connector_type is SDC).
    required: false
    type: str
  ignore_certificate:
    description: Whether to skip certificate validation when onboarding.
    required: false
    type: bool
    default: false
  grouped_labels:
    description: Mapping of grouped labels to assign to the device.
    required: false
    type: dict
  ungrouped_labels:
    description: List of free-form labels to assign to the device.
    required: false
    type: list
    elements: str
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
# Example 1: Using module_defaults (recommended)
- name: Onboard ASA devices
  hosts: all
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Onboard branch-asa-1
      cisco.sccfm.onboard_asa:
        name: branch-asa-1
        device_address: 192.0.2.10:443
        username: admin
        password: "{{ vault_asa_password }}"
        connector_type: SDC
        connector_name: branch-sdc-1
        ignore_certificate: true
        grouped_labels:
          site: ["branch-1"]
        ungrouped_labels:
          - asa
          - branch

# Example 2: Explicit parameters
- name: Onboard branch-asa-1
  cisco.sccfm.onboard_asa:
    name: branch-asa-1
    device_address: 192.0.2.10:443
    username: admin
    password: "{{ vault_asa_password }}"
    connector_type: SDC
    connector_name: branch-sdc-1
    region: us

# Example 3: Using the default configured profile
- name: Onboard branch-asa-1
  cisco.sccfm.onboard_asa:
    name: branch-asa-1
    device_address: 192.0.2.10:443
    username: admin
    password: "{{ vault_asa_password }}"
    connector_type: SDC
    connector_name: branch-sdc-1
"""

RETURN = r"""
device:
  description: The existing or newly onboarded ASA device.
  returned: always
  type: dict
"""


def build_argument_spec() -> dict[str, dict[str, str | bool | list[str]]]:
    return {
        "name": {"type": "str", "required": True},
        "device_address": {"type": "str", "required": True},
        "username": {"type": "str", "required": True},
        "password": {"type": "str", "required": True, "no_log": True},
        "connector_type": {
            "type": "str",
            "required": True,
            "choices": [ConnectorType.CDG, ConnectorType.SDC],
        },
        "connector_name": {"type": "str", "required": False},
        "ignore_certificate": {"type": "bool", "required": False, "default": False},
        "grouped_labels": {"type": "dict", "required": False},
        "ungrouped_labels": {"type": "list", "elements": "str", "required": False},
        **base_argument_spec(),
    }


def build_asa_input(
    params: dict[str, str | bool | list[str] | dict[str, list[str]] | None],
) -> AsaCreateOrUpdateInput:
    """Build AsaCreateOrUpdateInput from Ansible module parameters."""
    return AsaCreateOrUpdateInput(
        name=str(params["name"]),
        deviceAddress=str(params["device_address"]),
        username=str(params["username"]),
        password=str(params["password"]),
        connectorType=(
            ConnectorType.SDC if str(params["connector_type"]) == "SDC" else ConnectorType.CDG
        ),
        connectorName=str(params.get("connector_name")) if params.get("connector_name") else None,
        ignoreCertificate=bool(params.get("ignore_certificate", False)),
        labels=Labels(
            groupedLabels=params.get("grouped_labels"),
            ungroupedLabels=params.get("ungrouped_labels"),
        ),
    )


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
        required_if=[("connector_type", "SDC", ["connector_name"])],
    )

    config: Config = create_config(module)
    params = module.params
    asa_create_or_update_input = build_asa_input(params)
    try:
        # Business logic
        existing_device_opt = _get_existing_device(
            config=config, asa_create_or_update_input=asa_create_or_update_input
        )
        if existing_device_opt is not None:
            module.exit_json(
                changed=False,
                msg="ASA device already exists",
                device=existing_device_opt.to_dict(),
            )

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Would onboard ASA device '{asa_create_or_update_input.name}'",
                device={},
            )

        asa_device = _onboard_asa(config, asa_create_or_update_input)
        module.exit_json(changed=True, msg="Onboarded successfully", device=asa_device.to_dict())
    except ApiException as e:
        error = SccApiError.from_exception(e)
        module.fail_json(**error.to_dict())
    except Exception as e:
        module.fail_json(msg=f"Unexpected error: {str(e)}")


def _onboard_asa(config: ConfigLike, asa_create_or_update_input: AsaCreateOrUpdateInput) -> Device:
    try:
        asa_onboard_service = AsaOnboardService(config=config)
        return asa_onboard_service.onboard_asa(
            asa_create_or_update_input=asa_create_or_update_input
        )
    except Exception as e:
        raise e


def _get_existing_device(
    config: ConfigLike, asa_create_or_update_input: AsaCreateOrUpdateInput
) -> Optional[Device]:
    try:
        inventory_service = InventoryService(config=config)
        device_page: DevicePage = inventory_service.get_devices(
            limit=1,
            offset=0,
            query=f"{ASA_DEVICE_TYPE_FILTER} AND name:{asa_create_or_update_input.name}",
        )
        return device_page.items[0] if device_page.count > 0 else None
    except Exception as e:
        raise e


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

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

from sccfm_core import InventoryService, SccApiError
from sccfm_core.services.inventory import AsaOnboardService
from sccfm_core.types import ConfigLike

from ..module_utils.config import Config

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
# Example 1: Using module_defaults (recommended)
- name: Onboard ASA devices
  hosts: all
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
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
    api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"

# Example 3: Using environment variables (SCCFM_REGION and SCCFM_API_TOKEN)
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
payload:
  description: Structured payload matching the ASA onboarding API.
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
        "region": {"type": "str", "required": False},
        "api_token": {"type": "str", "required": False, "no_log": True},
    }


def build_asa_input(
    params: dict[str, str | bool | list[str] | dict[str, list[str]] | None],
) -> AsaCreateOrUpdateInput:
    """Build AsaCreateOrUpdateInput from Ansible module parameters.

    Uses model_construct to skip Pydantic validation, allowing empty
    passwords (e.g. vASA devices with no password set).
    """
    return AsaCreateOrUpdateInput.model_construct(
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

    try:
        config = Config(
            region=module.params.get("region") or "",
            api_token=module.params.get("api_token") or "",
        )
    except ValueError as e:
        module.fail_json(msg=str(e))

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
        module.exit_json(changed=True, msg="Onboarded successfulyl", device=asa_device.to_dict())
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
            limit=1, offset=0, query=f"deviceType:ASA AND name:{asa_create_or_update_input.name}"
        )
        return device_page.items[0] if device_page.count > 0 else None
    except Exception as e:
        raise e


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

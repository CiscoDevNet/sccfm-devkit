from __future__ import annotations

import os

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import AsaCreateOrUpdateInput, ConnectorType, Device, Labels

from sccfm_core.services.inventory import AsaOnboardService

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
    description: SCCFM region (int, us, eu, apj, aus, uae, or in).
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


def validate_connection_params(module: AnsibleModule) -> tuple[str, str]:
    """Validate and retrieve region and api_token from params or environment."""
    region = module.params.get("region") or os.getenv("SCCFM_REGION")
    api_token = module.params.get("api_token") or os.getenv("SCCFM_API_TOKEN")

    if not region:
        module.fail_json(
            msg="region is required. Provide it via module parameter, module_defaults, or "
            "SCCFM_REGION environment variable."
        )
    if not api_token:
        module.fail_json(
            msg="api_token is required. Provide it via module parameter, module_defaults, or "
            "SCCFM_API_TOKEN environment variable."
        )

    return region, api_token


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
        required_if=[("connector_type", "SDC", ["connector_name"])],
    )

    region, api_token = validate_connection_params(module)

    try:
        config = Config(region=region, api_token=api_token)
    except ValueError as e:
        module.fail_json(msg=str(e))

    params = module.params
    asa_create_or_update_input = build_asa_input(params)

    try:
        # Business logic
        asa_onboard_service = AsaOnboardService(config=config)
        asa_device: Device = asa_onboard_service.onboard_asa(
            asa_create_or_update_input=asa_create_or_update_input
        )
    except Exception as e:
        module.fail_json(msg=f"Failed to onboard ASA: {str(e)}")

    module.exit_json(changed=True, device=asa_device.to_dict(), region=region)


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

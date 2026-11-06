# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import SccApiError
from cisco_sccfm_core.services.inventory.cdfmc_platform_settings_policy_service import (
    CdfmcPlatformSettingsPolicyService,
)

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: assign_cdfmc_platform_settings_policy
short_description: Assign a cdFMC platform settings policy to an FTD device by name
description:
  - Look up an existing FTD platform settings policy by name and an FTD device by
    name in cloud-delivered FMC, then assign the policy to that device.
  - Idempotent - if the device is already a target of the policy's assignment,
    no write is made (C(changed=false)).
  - >-
    WARNING: this module has not yet been exercised against a live cdFMC
    tenant. It mirrors FMC's documented "Policy Assignments" REST contract
    (the same assignment model used for NAT, QoS, health, and platform
    settings policies), but has not been confirmed with a real
    request/response. Confirm behavior via API Explorer before relying on
    this in production.
options:
  domain_uid:
    description: >-
      cdFMC domain UID. Obtain this from C(fmc_domain_uid) returned by C(list_managers).
    required: true
    type: str
  policy_name:
    description: Name of the platform settings policy as it appears in cdFMC.
    required: true
    type: str
  device_name:
    description: Name of the FTD device as registered in cdFMC.
    required: true
    type: str
  region:
    description: SCCFM region (int, us, eu, apj, au, uae, in, or ci).
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
- name: Assign platform settings policy to vFTD
  cisco.sccfm.assign_cdfmc_platform_settings_policy:
    domain_uid: "{{ cdfmc_domain_uid }}"
    policy_name: "Lab Platform Settings"
    device_name: "vftd-a"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
"""

RETURN = r"""
assignment:
  description: The resulting policy assignment.
  returned: success
  type: dict
  contains:
    assignment_id:
      description: Unique identifier of the policy assignment in cdFMC.
      type: str
    policy_uid:
      description: Unique identifier of the platform settings policy.
      type: str
    policy_name:
      description: Name of the platform settings policy, as given.
      type: str
    device_id:
      description: Unique identifier of the target FTD device.
      type: str
    target_ids:
      description: Unique identifiers of all devices currently targeted by this policy.
      type: list
      elements: str
    already_assigned:
      description: Whether the device was already a target of this policy before this run.
      type: bool
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "domain_uid": {"type": "str", "required": True},
        "policy_name": {"type": "str", "required": True},
        "device_name": {"type": "str", "required": True},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config = create_config(module)
    params = module.params

    domain_uid: str = params["domain_uid"]
    policy_name: str = params["policy_name"]
    device_name: str = params["device_name"]

    try:
        service = CdfmcPlatformSettingsPolicyService(config=config)
        policy_uid = service.get_policy_uid_by_name(domain_uid, policy_name)
        device_id = service.get_fmc_device_id(domain_uid, device_name)

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=(
                    f"Would assign platform settings policy '{policy_name}' "
                    f"to device '{device_name}'"
                ),
                assignment={},
            )
            return

        result = service.assign_policy_to_device(
            domain_uid, policy_uid, policy_name, device_id
        )
        module.exit_json(
            changed=not result.already_assigned,
            msg=(
                f"Device '{device_name}' is already a target of platform "
                f"settings policy '{policy_name}'"
                if result.already_assigned
                else (
                    f"Assigned platform settings policy '{policy_name}' to "
                    f"device '{device_name}'"
                )
            ),
            assignment={
                "assignment_id": result.assignment_id,
                "policy_uid": result.policy_uid,
                "policy_name": result.policy_name,
                "device_id": result.device_id,
                "target_ids": result.target_ids,
                "already_assigned": result.already_assigned,
            },
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to assign platform settings policy: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

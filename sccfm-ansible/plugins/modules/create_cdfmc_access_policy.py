# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import SccApiError
from cisco_sccfm_core.services.inventory.cdfmc_access_policy_service import (
    CdfmcAccessPolicyService,
)

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: create_cdfmc_access_policy
short_description: Create an access control policy on a cdFMC domain from a caller-supplied payload
description:
  - Create a new FMC access control policy on cloud-delivered FMC, using a caller-supplied
    payload for the policy body (e.g. C(defaultAction), C(description)).
  - C(name) is always forced onto the payload (overriding anything given there for C(name)
    or C(type)), so callers can tie the policy's name to a device name or other convention
    without having to repeat it inside the payload itself.
  - Idempotent - if a policy with the same name already exists it is returned unchanged and
    the payload is not sent.
options:
  domain_uid:
    description: >-
      cdFMC domain UID. Obtain this from C(fmc_domain_uid) returned by C(list_managers).
    required: true
    type: str
  name:
    description: Name of the access control policy to create (or reuse, if it already exists).
    required: true
    type: str
  payload:
    description: >-
      Raw FMC AccessPolicy fields to send when creating the policy (e.g. C(defaultAction),
      C(description)). C(name) and C(type) in this dict, if present, are ignored/overridden.
      Only used when the policy does not already exist.
    required: false
    type: dict
    default: {}
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
- name: Create an access control policy named after a vFTD
  cisco.sccfm.create_cdfmc_access_policy:
    domain_uid: "{{ cdfmc_domain_uid }}"
    name: "{{ item.name }}-AC"
    payload: "{{ item.access_control_policy_payload }}"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: ac_policy_result

- name: Use the created policy's uid when onboarding the device
  cisco.sccfm.onboard_cdfmc_ftd:
    name: "{{ item.name }}"
    fmc_access_policy_uid: "{{ ac_policy_result.access_policy.uid }}"
    licenses: ["BASE"]
    profile: default
"""

RETURN = r"""
access_policy:
  description: The created or existing access control policy.
  returned: success
  type: dict
  contains:
    uid:
      description: Unique identifier of the access policy in cdFMC.
      type: str
    name:
      description: Name of the access policy.
      type: str
changed:
  description: True if the policy was newly created, False if it already existed.
  returned: always
  type: bool
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "domain_uid": {"type": "str", "required": True},
        "name": {"type": "str", "required": True},
        "payload": {"type": "dict", "required": False, "default": {}},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config = create_config(module)
    domain_uid: str = module.params["domain_uid"]
    name: str = module.params["name"]
    payload: dict = module.params["payload"] or {}

    try:
        service = CdfmcAccessPolicyService(config=config)
        existing_page = service.get_access_policies(domain_uid, limit=200)
        existing = next((p for p in existing_page.items if p.name == name), None)

        if existing is not None:
            module.exit_json(
                changed=False,
                msg=f"Access control policy '{name}' already exists",
                access_policy={"uid": existing.uid, "name": existing.name},
            )
            return

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Would create access control policy '{name}'",
                access_policy={},
            )
            return

        policy = service.create_access_policy(domain_uid, name, payload)
        module.exit_json(
            changed=True,
            msg=f"Successfully created access control policy '{name}'",
            access_policy={"uid": policy.uid, "name": policy.name},
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to create access control policy: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.constants import (
    DEFAULT_POLLING_INTERVAL_SEC,
    DEFAULT_TRANSACTION_TIMEOUT_SEC,
)
from cisco_sccfm_core.errors import SccApiError
from cisco_sccfm_core.services.inventory.cdfmc_access_policy_service import (
    CdfmcAccessPolicyService,
)

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: clone_cdfmc_access_policy
short_description: Clone an existing access control policy on a cdFMC domain
description:
  - Clone an existing FMC access control policy on cloud-delivered FMC into a new policy
    with a different name, via cdFMC's C(clonepolicies) operation.
  - Unlike C(create_cdfmc_access_policy) (which builds a new policy from a caller-supplied
    payload), cloning carries over the source policy's full configuration as cdFMC itself
    understands it - including sub-resources a plain POST create does not populate, such as
    the "Network Analysis and Intrusion Policies" advanced settings. Use this when you want
    a new policy to start out identically configured to an already-correct reference policy.
  - This operation is asynchronous on the cdFMC side - this module submits the clone and
    polls until the underlying job completes before returning.
  - Idempotent - if a policy named C(clone_name) already exists it is returned unchanged and
    no clone is submitted.
options:
  domain_uid:
    description: >-
      cdFMC domain UID. Obtain this from C(fmc_domain_uid) returned by C(list_managers).
    required: true
    type: str
  source_policy_id:
    description: UID of the existing access control policy to clone.
    required: true
    type: str
  clone_name:
    description: Name for the new, cloned access control policy.
    required: true
    type: str
  polling_interval_sec:
    description: Seconds to wait between polls of the clone job's status.
    required: false
    type: int
  timeout_sec:
    description: Maximum seconds to wait for the clone job to complete.
    required: false
    type: int
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
  - Cisco SCCFM Team (@CiscoDevNet)
"""

EXAMPLES = r"""
- name: Clone a known-good reference policy for a new vFTD
  cisco.sccfm.clone_cdfmc_access_policy:
    domain_uid: "{{ cdfmc_domain_uid }}"
    source_policy_id: "{{ source_policy_uid }}"
    clone_name: "{{ item.name }}-AC-BPR-2-4-5"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: ac_policy_result

- name: Use the cloned policy's uid when onboarding the device
  cisco.sccfm.onboard_cdfmc_ftd:
    name: "{{ item.name }}"
    fmc_access_policy_uid: "{{ ac_policy_result.access_policy.uid }}"
    licenses: ["BASE"]
    profile: default
"""

RETURN = r"""
access_policy:
  description: The cloned (or already-existing) access control policy.
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
  description: True if a new clone was created, False if a policy with this name already existed.
  returned: always
  type: bool
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "domain_uid": {"type": "str", "required": True},
        "source_policy_id": {"type": "str", "required": True},
        "clone_name": {"type": "str", "required": True},
        "polling_interval_sec": {"type": "int", "required": False},
        "timeout_sec": {"type": "int", "required": False},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config = create_config(module)
    domain_uid: str = module.params["domain_uid"]
    source_policy_id: str = module.params["source_policy_id"]
    clone_name: str = module.params["clone_name"]
    polling_interval_sec = module.params["polling_interval_sec"] or DEFAULT_POLLING_INTERVAL_SEC
    timeout_sec = module.params["timeout_sec"] or DEFAULT_TRANSACTION_TIMEOUT_SEC

    try:
        service = CdfmcAccessPolicyService(config=config)
        existing_page = service.get_access_policies(domain_uid, limit=200)
        existing = next((p for p in existing_page.items if p.name == clone_name), None)

        if existing is not None:
            module.exit_json(
                changed=False,
                msg=f"Access control policy '{clone_name}' already exists",
                access_policy={"uid": existing.uid, "name": existing.name},
            )
            return

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Would clone access control policy '{source_policy_id}' as '{clone_name}'",
                access_policy={},
            )
            return

        policy = service.clone_access_policy(
            domain_uid,
            source_policy_id,
            clone_name,
            polling_interval_sec=polling_interval_sec,
            timeout_sec=timeout_sec,
        )
        module.exit_json(
            changed=True,
            msg=f"Successfully cloned access control policy '{source_policy_id}' as '{clone_name}'",
            access_policy={"uid": policy.uid, "name": policy.name},
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to clone access control policy: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

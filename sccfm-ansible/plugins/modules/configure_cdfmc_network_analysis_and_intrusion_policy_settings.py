# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import SccApiError
from cisco_sccfm_core.services.inventory.cdfmc_network_analysis_intrusion_policy_setting_service import (
    CdfmcNetworkAnalysisAndIntrusionPolicySettingService,
)

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: configure_cdfmc_network_analysis_and_intrusion_policy_settings
short_description: Configure the "Network Analysis and Intrusion Policies" advanced settings of an access control policy
description:
  - Sets the "Intrusion Policy used before Access Control rule is determined" (base IPS
    policy + its variable set) and "Default Network Analysis Policy" on an FMC access
    control policy's advanced settings.
  - This endpoint is not documented in the public cdFMC OpenAPI spec as of 2026-11; it was
    reverse-engineered from a real PUT request captured via browser devtools while editing
    this exact panel in the FMC/CDO UI. Confirmed working against a live tenant (the UI's
    own save used this same path/payload shape).
  - Idempotent - if the policy's setting already references the same base_ips_policy,
    base_ips_variable_set, and default_network_analysis_policy (by uid), no write is made.
  - Callers are responsible for resolving object names to C(uid)s for the current domain
    first (e.g. via C(list_cdfmc_intrusion_policies), C(list_cdfmc_variable_sets),
    C(list_cdfmc_network_analysis_policies)) - this module does not resolve names itself,
    since these are domain/tenant-scoped objects whose UID differs per domain.
options:
  domain_uid:
    description: >-
      cdFMC domain UID. Obtain this from C(fmc_domain_uid) returned by C(list_managers).
    required: true
    type: str
  policy_id:
    description: UID of the access control policy to configure.
    required: true
    type: str
  base_ips_policy:
    description: >-
      Reference to the Intrusion Policy used before the Access Control rule is determined,
      as C({uid: ..., name: ...}). Resolve C(uid) via C(list_cdfmc_intrusion_policies) first.
    required: true
    type: dict
  base_ips_variable_set:
    description: >-
      Reference to the variable set used alongside C(base_ips_policy), as
      C({uid: ..., name: ...}). Resolve C(uid) via C(list_cdfmc_variable_sets) first.
    required: true
    type: dict
  default_network_analysis_policy:
    description: >-
      Reference to the Default Network Analysis Policy, as C({uid: ..., name: ...}).
      Resolve C(uid) via C(list_cdfmc_network_analysis_policies) first (Network Analysis
      Policy is a distinct resource type from Intrusion Policy, even though FMC ships
      same-named default pairs of the two).
    required: true
    type: dict
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
- name: Configure Network Analysis and Intrusion Policy settings on a created AC policy
  cisco.sccfm.configure_cdfmc_network_analysis_and_intrusion_policy_settings:
    domain_uid: "{{ cdfmc_domain_uid }}"
    policy_id: "{{ ac_policy_result.access_policy.uid }}"
    base_ips_policy:
      uid: "6c66b83c-bc23-55b6-879d-c4d847443503"
      name: "Balanced Security and Connectivity"
    base_ips_variable_set:
      uid: "76fa83ea-c972-11e2-8be8-8e45bb1343c0"
      name: "Default-Set"
    default_network_analysis_policy:
      uid: "db7dc865-16b5-5eab-8b5a-c85f3a61690b"
      name: "Balanced Security and Connectivity"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
"""

RETURN = r"""
setting:
  description: The full, updated Network Analysis and Intrusion Policy setting object.
  returned: success
  type: dict
changed:
  description: True if a write was made, False if the setting already matched.
  returned: always
  type: bool
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "domain_uid": {"type": "str", "required": True},
        "policy_id": {"type": "str", "required": True},
        "base_ips_policy": {"type": "dict", "required": True},
        "base_ips_variable_set": {"type": "dict", "required": True},
        "default_network_analysis_policy": {"type": "dict", "required": True},
        **base_argument_spec(),
    }


def _reference(ref: dict, type_name: str) -> dict:
    return {"id": ref["uid"], "name": ref.get("name"), "type": type_name}


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config = create_config(module)
    domain_uid: str = module.params["domain_uid"]
    policy_id: str = module.params["policy_id"]
    base_ips_policy = module.params["base_ips_policy"]
    base_ips_variable_set = module.params["base_ips_variable_set"]
    default_nap = module.params["default_network_analysis_policy"]

    try:
        service = CdfmcNetworkAnalysisAndIntrusionPolicySettingService(config=config)
        existing = service.get_setting(domain_uid, policy_id)
        current_base_inspection = existing.get("baseInspection") or {}
        current_network_analysis = existing.get("networkAnalysis") or {}

        already_matches = (
            (current_base_inspection.get("baseIpsPolicy") or {}).get("id")
            == base_ips_policy["uid"]
            and (current_base_inspection.get("baseIpsVariableSet") or {}).get("id")
            == base_ips_variable_set["uid"]
            and (current_network_analysis.get("defaultNetworkAnalysisPolicy") or {}).get("id")
            == default_nap["uid"]
        )

        if already_matches:
            module.exit_json(
                changed=False,
                msg="Network Analysis and Intrusion Policy settings already match",
                setting=existing,
            )
            return

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg="Would update Network Analysis and Intrusion Policy settings",
                setting={},
            )
            return

        updated = service.update_setting(
            domain_uid,
            policy_id,
            base_ips_policy=_reference(base_ips_policy, "IntrusionPolicy"),
            base_ips_variable_set=_reference(base_ips_variable_set, "VariableSet"),
            default_network_analysis_policy=_reference(default_nap, "NetworkAnalysisPolicy"),
        )
        module.exit_json(
            changed=True,
            msg="Updated Network Analysis and Intrusion Policy settings",
            setting=updated,
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except Exception as e:
        module.fail_json(
            msg=f"Failed to configure Network Analysis and Intrusion Policy settings: {str(e)}"
        )


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

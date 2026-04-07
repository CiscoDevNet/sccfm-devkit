from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from scc_firewall_manager_sdk import ApiException

from sccfm_core import SccApiError
from sccfm_core.services.inventory.cdfmc_access_policy_service import CdfmcAccessPolicyService

from ..module_utils.config import base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: list_cdfmc_access_policies
short_description: List FMC access policies for a cdFMC domain
description:
  - List access policies available on the cloud-delivered FMC for a given domain.
  - Use C(list_managers) first to obtain the C(fmc_domain_uid) of the cdFMC.
options:
  domain_uid:
    description: >-
      The FMC domain UID to query. Obtain this from the C(fmc_domain_uid) field
      returned by the C(list_managers) module.
    required: true
    type: str
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
# Example 1: List access policies for a domain
- name: List cdFMC access policies
  cisco.sccfm.list_cdfmc_access_policies:
    domain_uid: "e276abec-e0f2-11e3-8169-6d9ed49b625f"
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: result

- name: Show access policies
  ansible.builtin.debug:
    var: result.access_policies
"""

RETURN = r"""
access_policies:
  description: List of FMC access policies in the given domain.
  returned: success
  type: list
  elements: dict
  contains:
    uid:
      description: Unique identifier of the access policy. Use as C(fmc_access_policy_uid).
      type: str
    name:
      description: Name of the access policy.
      type: str
count:
  description: Number of access policies returned.
  returned: success
  type: int
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "domain_uid": {"type": "str", "required": True},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    if module.check_mode:
        module.exit_json(changed=False, access_policies=[], count=0)
        return

    config = create_config(module)

    try:
        service = CdfmcAccessPolicyService(config)
        policies = service.get_access_policies(module.params["domain_uid"])
        access_policies = [{"uid": p.uid, "name": p.name} for p in policies]
        module.exit_json(
            changed=False,
            access_policies=access_policies,
            count=len(access_policies),
        )
    except ApiException as e:
        error = SccApiError.from_exception(e)
        module.fail_json(**error.to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to list access policies: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

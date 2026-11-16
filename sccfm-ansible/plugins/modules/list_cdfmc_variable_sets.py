# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

DOCUMENTATION = r"""
---
module: list_cdfmc_variable_sets
short_description: List FMC variable sets for a cdFMC domain
description:
  - List variable sets available on the cloud-delivered FMC for a given domain.
  - Variable sets are domain-scoped - the same name (e.g. "Default-Set") exists in every
    cdFMC domain under a different UID, so use this to resolve a UID by name for the
    current domain/tenant instead of hardcoding one copied from a different domain.
  - Use C(list_managers) first to obtain the C(fmc_domain_uid) of the cdFMC.
options:
  domain_uid:
    description: >-
      The FMC domain UID to query. Obtain this from the C(fmc_domain_uid) field
      returned by the C(list_managers) module.
    required: true
    type: str
  limit:
    description: Maximum number of variable sets to return.
    required: false
    type: int
    default: 200
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
  - Cisco SCCFM Team (@CiscoDevNet)
"""

EXAMPLES = r"""
- name: List cdFMC variable sets
  cisco.sccfm.list_cdfmc_variable_sets:
    domain_uid: "e276abec-e0f2-11e3-8169-6d9ed49b625f"
    profile: default
  register: result

- name: Resolve the default variable set's UID by name
  ansible.builtin.set_fact:
    default_variable_set_uid: >-
      {{ result.variable_sets | selectattr('name', 'equalto', 'Default-Set')
         | map(attribute='uid') | first }}
"""

RETURN = r"""
variable_sets:
  description: List of FMC variable sets in the given domain.
  returned: success
  type: list
  elements: dict
  contains:
    uid:
      description: Unique identifier of the variable set.
      type: str
    name:
      description: Name of the variable set.
      type: str
"""


from typing import Any

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException

    from cisco_sccfm_core import SccApiError
    from cisco_sccfm_core.services.inventory.cdfmc_variable_set_service import (
        CdfmcVariableSetService,
    )
except ImportError as exc:
    record_import_error(exc)
    ApiException = RuntimeError


from ..module_utils.config import base_argument_spec, create_config


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "domain_uid": {"type": "str", "required": True},
        "limit": {"type": "int", "required": False, "default": 200},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config = create_config(module)

    try:
        service = CdfmcVariableSetService(config)
        variable_sets = service.list_variable_sets(
            module.params["domain_uid"],
            limit=module.params["limit"],
        )
        module.exit_json(
            changed=False,
            variable_sets=[{"uid": vs.uid, "name": vs.name} for vs in variable_sets],
        )
    except ApiException as e:
        error = SccApiError.from_exception(e)
        module.fail_json(**error.to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to list variable sets: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

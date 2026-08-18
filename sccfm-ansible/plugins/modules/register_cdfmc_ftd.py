# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.dependencies import record_import_error

try:
    from scc_firewall_manager_sdk import ApiException, Device

    from cisco_sccfm_core import SccApiError
    from cisco_sccfm_core.services.inventory import FtdRegisterService
except ImportError as exc:
    record_import_error(exc)
    ApiException = NotFoundError = FtdConfigureManagerError = RuntimeError


from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""
---
module: register_cdfmc_ftd
short_description: Complete registration of a cdFMC-managed FTD device to SCC Firewall Manager
description:
  - Completes the registration of an FTD device with its cdFMC manager after the CLI key has
    been pasted on the device. Call this module after C(cisco.sccfm.configure_manager) succeeds.
  - Returns a transaction and waits for it to reach DONE status.
options:
  ftd_uid:
    description:
      - The UID of the FTD device in SCC Firewall Manager to register.
    required: true
    type: str
  skip_initial_deployment:
    description:
      - If true, the initial configuration deployment to the device is skipped after registration.
    required: false
    type: bool
    default: false
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
- name: Register vFTD with cdFMC using shared authentication defaults
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  tasks:
    - name: Complete the FTD registration
      cisco.sccfm.register_cdfmc_ftd:
        ftd_uid: "{{ ftd_onboard_result.device.uid }}"
"""

RETURN = r"""
device:
  description:
    - The registered FTD device record from SCC Firewall Manager.
  returned: always
  type: dict
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "ftd_uid": {"type": "str", "required": True},
        "skip_initial_deployment": {"type": "bool", "required": False, "default": False},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    config: Config = create_config(module)
    ftd_uid: str = module.params["ftd_uid"]
    skip_initial_deployment: bool = module.params["skip_initial_deployment"]

    if module.check_mode:
        module.exit_json(
            changed=True,
            msg=f"Would register FTD device '{ftd_uid}' with cdFMC.",
            device={},
        )
        return

    try:
        register_service = FtdRegisterService(config=config)
        device: Device = register_service.register_ftd(
            ftd_uid=ftd_uid,
            skip_initial_deployment=skip_initial_deployment,
        )

        module.exit_json(
            changed=True,
            msg=f"FTD device '{ftd_uid}' registered with cdFMC successfully.",
            device=device.to_dict(),
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

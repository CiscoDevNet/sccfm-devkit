# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule, env_fallback

from cisco_sccfm_core.services.inventory import (
    FtdConfigureManagerError,
    FtdConfigureManagerService,
    parse_jump_host,
)

DOCUMENTATION = r"""
---
module: configure_manager
short_description: Complete cdFMC-managed FTD onboarding by registering the FTD over SSH
description:
  - SSH into an FTD VM and run the C(configure manager add ...) command produced by
    C(onboard_cdfmc_ftd).
  - This is the final onboarding step; it tells the FTD to phone home to the cdFMC and register.
  - This module talks directly to the device over SSH (paramiko). It does NOT call the SCCFM API,
    so it does not take C(region) or C(api_token) and is not part of the
    C(cisco.sccfm.all) action group.
  - Only works if the FTD is reachable on its SSH port (C(ftd_port), default 22) from the host
    running this module, or from the jump host when C(jump_host) is set.
  - The FTD sees the connection from the SSH client's source IP, so that IP must be on the FTD
    ssh-access-list. When a jump host is used, that source is the jump host's IP.
options:
  ftd_host:
    description: Management IP address or hostname of the FTD VM.
    required: true
    type: str
  ftd_port:
    description: SSH port of the FTD VM.
    required: false
    type: int
    default: 22
  ftd_user:
    description: SSH username for the FTD VM.
    required: true
    type: str
  ftd_password:
    description:
      - SSH password for the FTD VM.
      - Can also be supplied via the C(SCCFM_FTD_PASSWORD) environment variable.
    required: false
    type: str
    env:
      - name: SCCFM_FTD_PASSWORD
  cli_key:
    description:
      - The full C(configure manager add ...) string returned by C(onboard_cdfmc_ftd).
      - Must be a single line that starts with C(configure manager add).
    required: true
    type: str
  jump_host:
    description:
      - Optional bastion to tunnel through, as C([user@]host[:port]).
      - When set, the FTD sees the connection from the jump host's IP, so that IP must be on the
        FTD ssh-access-list.
    required: false
    type: str
  jump_password:
    description:
      - Password for the jump host.
      - Can also be supplied via the C(SCCFM_JUMP_PASSWORD) environment variable.
      - Leave unset to use SSH key/agent authentication for the jump host.
    required: false
    type: str
    env:
      - name: SCCFM_JUMP_PASSWORD
  ssh_timeout:
    description: SSH connect and read timeout in seconds.
    required: false
    type: int
    default: 30
author:
  - Cisco SCCFM Team
"""

EXAMPLES = r"""
# Example 1: Direct SSH to the FTD
- name: Register FTD with its cdFMC manager
  cisco.sccfm.configure_manager:
    ftd_host: "203.0.113.10"
    ftd_user: admin
    ftd_password: "{{ vault_ftd_password }}"
    cli_key: "{{ onboard_result.cli_key }}"

# Example 2: Through a jump host (bastion)
- name: Register FTD via a bastion
  cisco.sccfm.configure_manager:
    ftd_host: "203.0.113.10"
    ftd_user: admin
    ftd_password: "{{ vault_ftd_password }}"
    jump_host: "bastion@203.0.113.5:2222"
    jump_password: "{{ vault_jump_password }}"
    cli_key: "{{ onboard_result.cli_key }}"

# Example 3: Jump host with SSH key/agent auth (no jump_password)
- name: Register FTD via a bastion using key auth
  cisco.sccfm.configure_manager:
    ftd_host: "203.0.113.10"
    ftd_user: admin
    ftd_password: "{{ vault_ftd_password }}"
    jump_host: "bastion@203.0.113.5:2222"
    cli_key: "{{ onboard_result.cli_key }}"

# Example 4: Chained after onboarding
- name: Onboard FTD
  cisco.sccfm.onboard_cdfmc_ftd:
    name: "Branch FTD"
    fmc_access_policy_uid: "{{ fmc_access_policy_uid }}"
    licenses:
      - BASE
    region: "{{ sccfm_region }}"
    api_token: "{{ sccfm_api_token }}"
  register: onboard_result

- name: Complete registration over SSH
  cisco.sccfm.configure_manager:
    ftd_host: "203.0.113.10"
    ftd_user: admin
    ftd_password: "{{ vault_ftd_password }}"
    cli_key: "{{ onboard_result.cli_key }}"
"""

RETURN = r"""
host:
  description: The FTD host the command was run against.
  returned: success
  type: str
success:
  description: Whether the FTD confirmed the manager configuration.
  returned: success
  type: bool
output:
  description: The device output captured from the FTD CLI, with echoed manager commands removed.
  returned: success
  type: str
msg:
  description: Human-readable result message.
  returned: always
  type: str
"""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "ftd_host": {"type": "str", "required": True},
        "ftd_port": {"type": "int", "required": False, "default": 22},
        "ftd_user": {"type": "str", "required": True},
        "ftd_password": {
            "type": "str",
            "required": False,
            "no_log": True,
            "fallback": (env_fallback, ["SCCFM_FTD_PASSWORD"]),
        },
        "cli_key": {"type": "str", "required": True, "no_log": True},
        "jump_host": {"type": "str", "required": False},
        "jump_password": {
            "type": "str",
            "required": False,
            "no_log": True,
            "fallback": (env_fallback, ["SCCFM_JUMP_PASSWORD"]),
        },
        "ssh_timeout": {"type": "int", "required": False, "default": 30},
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )

    host: str = module.params["ftd_host"]
    port: int = module.params["ftd_port"]
    username: str = module.params["ftd_user"]
    password: str | None = module.params.get("ftd_password")
    cli_key: str = module.params["cli_key"]
    jump_host: str | None = module.params.get("jump_host")
    jump_password: str | None = module.params.get("jump_password")
    timeout: int = module.params["ssh_timeout"]

    jump = None
    if jump_host:
        try:
            jump = parse_jump_host(jump_host, jump_password or None)
        except ValueError as exc:
            module.fail_json(msg=str(exc))
            return

    if module.check_mode:
        module.exit_json(
            changed=True,
            msg=f"Would configure manager on FTD {host}:{port}.",
            host=host,
            output="",
        )
        return

    if not password:
        module.fail_json(
            msg=(
                "ftd_password is required. Provide it via the module parameter or the "
                "SCCFM_FTD_PASSWORD environment variable."
            )
        )
        return

    try:
        service = FtdConfigureManagerService()
        result = service.configure_manager(
            host=host,
            port=port,
            username=username,
            password=password,
            cli_key=cli_key,
            timeout=timeout,
            jump=jump,
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))
        return
    except FtdConfigureManagerError as exc:
        module.fail_json(msg=str(exc), output=exc.output, host=host, success=False)
        return

    module.exit_json(
        changed=True,
        msg=result.message,
        host=result.host,
        success=result.success,
        output=result.output,
    )


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Complete FTD registration by executing the one-time key over direct SSH."""

from __future__ import annotations

import os

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.ftd.phases.onboard_ftd import _CLI_KEY_STATE
from cisco_sccfm_cli.e2e.ftd.phases.test_data import (
    FTD_REGISTRATION_HOST,
    FTD_REGISTRATION_JUMP_HOST,
    FTD_REGISTRATION_PORT,
    FTD_REGISTRATION_SSH_TIMEOUT,
    FTD_REGISTRATION_USER,
)


def run(ctx: ProfileContext) -> None:
    cli_key = ctx.state.get(_CLI_KEY_STATE)
    args = [
        "inventory",
        "devices",
        "cdfmc-managed-ftd",
        "configure-manager",
        "--ftd-host",
        FTD_REGISTRATION_HOST,
        "--ftd-port",
        FTD_REGISTRATION_PORT,
        "--ftd-user",
        FTD_REGISTRATION_USER,
        "--ssh-timeout",
        str(FTD_REGISTRATION_SSH_TIMEOUT),
        "--format",
        "json",
    ]
    if FTD_REGISTRATION_JUMP_HOST:
        args.extend(("--jump-host", FTD_REGISTRATION_JUMP_HOST))
        if not os.environ.get("SCCFM_JUMP_PASSWORD"):
            args.extend(("--jump-password", ""))

    try:
        result = run_cli(
            *args,
            profile=ctx.profile,
            config_path=ctx.config_path,
            timeout=max(300, (FTD_REGISTRATION_SSH_TIMEOUT * 4) + 30),
            sensitive_values=(cli_key,),
            extra_env={"SCCFM_FTD_CLI_KEY": cli_key},
        )
        payload = get_json(result)
        assert cli_key not in result.stdout, "CLI key was echoed in configure-manager output"
        assert isinstance(payload, dict), f"Expected configure-manager object, got {payload!r}"
        assert payload.get("success") is True, f"FTD did not confirm manager setup: {payload!r}"
        assert payload.get("host") == FTD_REGISTRATION_HOST, f"Unexpected FTD host: {payload!r}"
    except Exception:
        # Verification consumes the key only after a successful SSH phase. Do
        # not retain it in memory when configuration fails.
        ctx.state.pop(_CLI_KEY_STATE, None)
        raise

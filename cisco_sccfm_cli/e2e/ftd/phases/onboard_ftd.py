# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Create the CLI registration-test FTD record and retain its one-time key."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.ftd.phases.test_data import (
    FTD_REGISTRATION_ACCESS_POLICY_UID,
    FTD_REGISTRATION_NAME,
    FTD_REGISTRATION_PERFORMANCE_TIER,
    validate_registration_name,
)
from cisco_sccfm_core.constants import DEFAULT_TRANSACTION_TIMEOUT_SEC

_CLI_KEY_STATE = "ftd_registration_cli_key"


def run(ctx: ProfileContext) -> None:
    validate_registration_name()
    result = run_cli(
        "inventory",
        "devices",
        "cdfmc-managed-ftd",
        "onboard",
        "--name",
        FTD_REGISTRATION_NAME,
        "--fmc-access-policy-uid",
        FTD_REGISTRATION_ACCESS_POLICY_UID,
        "--licenses",
        "BASE",
        "--virtual",
        "--performance-tier",
        FTD_REGISTRATION_PERFORMANCE_TIER,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
        redact_json_fields=("cli_key",),
        timeout=DEFAULT_TRANSACTION_TIMEOUT_SEC + 60,
    )
    payload = get_json(result)
    assert isinstance(payload, dict), "Expected onboarding JSON object"
    cli_key = payload.get("cli_key")
    assert isinstance(cli_key, str) and cli_key, "Onboarding did not return a CLI key"
    assert "\n" not in cli_key and "\r" not in cli_key, "CLI key must be a single line"
    assert cli_key.casefold().startswith(
        "configure manager add"
    ), "CLI key does not contain a configure-manager command"
    ctx.state.set(_CLI_KEY_STATE, cli_key)

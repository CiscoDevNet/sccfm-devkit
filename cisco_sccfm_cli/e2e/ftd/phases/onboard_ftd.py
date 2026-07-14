# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Create the CLI registration-test FTD record and retain its one-time key.

The onboard command returns a ``cli_key`` — the ``configure manager add ...``
string the FTD must run to phone home.  It is a one-time secret, so it is kept
only in process state (never written to disk or argv) and consumed by the
``configure_manager`` phase.  This phase also records that the freshly onboarded
device reports ``NOT_SYNCED``/``NO_CONFIG`` so ``verify_registration`` can assert
the state transition once the device registers.
"""

from __future__ import annotations

from cisco_sccfm_cli.e2e._payload import normalize_rows
from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.ftd.phases.test_data import (
    FTD_REGISTRATION_ACCESS_POLICY_UID,
    FTD_REGISTRATION_NAME,
    FTD_REGISTRATION_PERFORMANCE_TIER,
    FTD_REGISTRATION_QUERY,
    validate_registration_name,
)
from cisco_sccfm_core.constants import DEFAULT_TRANSACTION_TIMEOUT_SEC

# Process-local state keys shared with configure_manager / verify_registration.
_CLI_KEY_STATE = "ftd_registration_cli_key"
_PRE_CONFIG_STATE = "ftd_registration_pre_config_state"

# A device that has been onboarded but has not yet registered has no synced
# configuration.  Either value is an acceptable "before" state.
_UNSYNCED_STATES = frozenset({"NOT_SYNCED", "NO_CONFIG"})


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

    # Record the pre-registration config state so verify_registration can assert
    # the NOT_SYNCED -> synced transition.  A brand-new record must not already
    # be SYNCED.
    pre_state = _current_config_state(ctx)
    assert (
        pre_state in _UNSYNCED_STATES
    ), f"Newly onboarded FTD should be unsynced, got config_state={pre_state!r}"
    ctx.state.set(_PRE_CONFIG_STATE, pre_state)


def _current_config_state(ctx: ProfileContext) -> str | None:
    """Return the config_state of the registration FTD, or None if absent."""
    result = run_cli(
        "inventory",
        "devices",
        "cdfmc-managed-ftd",
        "list",
        "--query",
        FTD_REGISTRATION_QUERY,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    rows = normalize_rows(get_json(result))
    match = next((row for row in rows if row.get("name") == FTD_REGISTRATION_NAME), None)
    if match is None:
        return None
    state = match.get("config_state") or match.get("configState")
    return state if isinstance(state, str) else None

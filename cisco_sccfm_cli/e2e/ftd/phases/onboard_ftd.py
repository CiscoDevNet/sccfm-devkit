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
    FTD_CDFMC_MANAGER_QUERY,
    FTD_REGISTRATION_ACCESS_POLICY_NAME,
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
    access_policy_uid = FTD_REGISTRATION_ACCESS_POLICY_UID or _resolve_access_policy_uid(ctx)
    result = run_cli(
        "inventory",
        "devices",
        "cdfmc-managed-ftd",
        "onboard",
        "--name",
        FTD_REGISTRATION_NAME,
        "--fmc-access-policy-uid",
        access_policy_uid,
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


def _resolve_access_policy_uid(ctx: ProfileContext) -> str:
    """Discover the FMC access policy UID from the tenant's cdFMC.

    Used when FMC_ACCESS_POLICY_UID is not provided: look up the cdFMC manager
    to get its FMC domain UID, then list that domain's access policies.  When
    FMC_ACCESS_POLICY_NAME is set, pick the policy with that name; otherwise
    require exactly one so the choice is never ambiguous.
    """
    domain_uid = _resolve_cdfmc_domain_uid(ctx)
    result = run_cli(
        "inventory",
        "manager",
        "access-policies",
        "list",
        "--domain-uid",
        domain_uid,
        "--limit",
        "50",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    policies = normalize_rows(get_json(result))
    assert policies, (
        "No FMC access policies found on the cdFMC (domain "
        f"{domain_uid!r}); set FMC_ACCESS_POLICY_UID to override."
    )

    if FTD_REGISTRATION_ACCESS_POLICY_NAME:
        wanted = FTD_REGISTRATION_ACCESS_POLICY_NAME.casefold()
        matches = [p for p in policies if str(p.get("name", "")).casefold() == wanted]
        assert len(matches) == 1, (
            f"Expected exactly one FMC access policy named "
            f"{FTD_REGISTRATION_ACCESS_POLICY_NAME!r}, found {len(matches)}."
        )
        uid = matches[0].get("uid")
    else:
        assert len(policies) == 1, (
            f"cdFMC has {len(policies)} access policies; set FMC_ACCESS_POLICY_UID "
            "or FMC_ACCESS_POLICY_NAME to disambiguate."
        )
        uid = policies[0].get("uid")

    assert isinstance(uid, str) and uid, f"Resolved access policy has no UID: {policies!r}"
    return uid


def _resolve_cdfmc_domain_uid(ctx: ProfileContext) -> str:
    """Return the FMC domain UID of the tenant's single cdFMC manager."""
    result = run_cli(
        "inventory",
        "manager",
        "list",
        "--query",
        FTD_CDFMC_MANAGER_QUERY,
        "--limit",
        "50",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    managers = normalize_rows(get_json(result))
    domain_uids = [
        d
        for d in (m.get("fmc_domain_uid") or m.get("fmcDomainUid") for m in managers)
        if isinstance(d, str) and d
    ]
    unique = sorted(set(domain_uids))
    assert len(unique) == 1, (
        f"Expected exactly one cdFMC domain UID from query {FTD_CDFMC_MANAGER_QUERY!r}, "
        f"found {unique!r}. Set FMC_ACCESS_POLICY_UID to override."
    )
    return unique[0]

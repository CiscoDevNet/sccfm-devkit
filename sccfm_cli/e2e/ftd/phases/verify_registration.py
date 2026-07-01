# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Poll SCCFM until the newly registered FTD is ONLINE."""

from __future__ import annotations

import time
from typing import Any

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.ftd.phases.onboard_ftd import _CLI_KEY_STATE
from sccfm_cli.e2e.ftd.phases.test_data import (
    FTD_NOT_ON_VERSION,
    FTD_REGISTRATION_DELAY_SEC,
    FTD_REGISTRATION_NAME,
    FTD_REGISTRATION_QUERY,
    FTD_REGISTRATION_RETRIES,
)


def _online_device(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    devices = payload.get("devices")
    if not isinstance(devices, list) or len(devices) != 1:
        return None
    device = devices[0]
    if not isinstance(device, dict) or device.get("connectivity_state") != "ONLINE":
        return None
    return device


def run(ctx: ProfileContext) -> None:
    cli_key = ctx.state.get(_CLI_KEY_STATE)
    last_payload: Any = None
    try:
        for _ in range(FTD_REGISTRATION_RETRIES):
            result = run_cli(
                "inventory",
                "devices",
                "ftd",
                "list-not-on-version",
                "--query",
                FTD_REGISTRATION_QUERY,
                "--version",
                FTD_NOT_ON_VERSION,
                "--format",
                "json",
                profile=ctx.profile,
                config_path=ctx.config_path,
                sensitive_values=(cli_key,),
            )
            last_payload = get_json(result)
            device = _online_device(last_payload)
            if device is not None:
                assert device.get("name") == FTD_REGISTRATION_NAME
                assert device.get("uid"), f"Registered FTD {FTD_REGISTRATION_NAME!r} has no UID"
                return
            time.sleep(FTD_REGISTRATION_DELAY_SEC)

        raise AssertionError(
            f"FTD {FTD_REGISTRATION_NAME!r} did not become ONLINE after "
            f"{FTD_REGISTRATION_RETRIES} checks. Last payload: {last_payload!r}"
        )
    finally:
        ctx.state.pop(_CLI_KEY_STATE, None)

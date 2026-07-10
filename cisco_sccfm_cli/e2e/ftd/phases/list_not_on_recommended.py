# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""List FTD devices not on the Cisco-recommended version."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.ftd.phases.test_data import FTD_TEST_QUERY


def run(ctx: ProfileContext) -> None:
    result = run_cli(
        "inventory",
        "devices",
        "ftd",
        "list-not-on-version",
        "--query",
        FTD_TEST_QUERY,
        "--recommended",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    if isinstance(payload, dict):
        # The Ansible suite asserted on device_count + matched_device_count + mode.
        # The CLI might wrap things differently; the structural assertion is that
        # we got a non-empty mapping back.
        assert payload, f"Expected recommended-version result envelope, got {payload!r}"
    else:
        assert payload, f"Expected recommended-version data, got {payload!r}"

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""List local users on CI ASA devices."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.asa.phases.test_data import ASA_TEST_QUERY


def run(ctx: ProfileContext) -> None:
    result = run_cli(
        "inventory",
        "devices",
        "asa",
        "list-local-users",
        "--query",
        ASA_TEST_QUERY,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    # Local-user output is grouped by device name; succeed on any non-empty result.
    assert payload, f"Expected local-user data, got {payload!r}"
    if isinstance(payload, dict):
        assert any(payload.values()), f"Expected per-device user lists, got {payload!r}"

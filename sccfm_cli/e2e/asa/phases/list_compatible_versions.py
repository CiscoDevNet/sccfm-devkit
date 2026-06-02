# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""List compatible ASA software versions for CI devices."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.asa.phases.test_data import ASA_TEST_QUERY


def run(ctx: ProfileContext) -> None:
    result = run_cli(
        "inventory",
        "devices",
        "asa",
        "upgrade",
        "compatible-versions",
        "--query",
        ASA_TEST_QUERY,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    # Either a top-level common-versions list, a per-device map, or an
    # envelope object — the assertion is that we got *something* back.
    has_data = (
        bool(payload)
        if isinstance(payload, list)
        else (
            any(payload.get(k) for k in ("compatible_versions", "common_versions", "per_device"))
            if isinstance(payload, dict)
            else False
        )
    )
    assert has_data, f"Expected compatible version data, got {payload!r}"

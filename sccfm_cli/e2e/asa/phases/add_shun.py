# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Add shun entries on CI ASA devices using TEST-NET addresses."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e._sync import wait_for_synced
from sccfm_cli.e2e.asa.phases.test_data import ASA_TEST_QUERY, SHUN_TEST_SOURCE_IPS


def run(ctx: ProfileContext) -> None:
    # Shun add pushes a CLI script; the API rejects it on a NOT_SYNCED device.
    # The Ansible suite that runs before us can leave the ASA NOT_SYNCED, so
    # poll until the device finishes its post-Ansible sync before pushing.
    wait_for_synced(ctx, query=ASA_TEST_QUERY)

    args = ["inventory", "devices", "asa", "shun", "add", "--query", ASA_TEST_QUERY]
    for ip in SHUN_TEST_SOURCE_IPS:
        args += ["--source-ip", ip]
    args += ["--format", "json"]
    run_cli(*args, profile=ctx.profile, config_path=ctx.config_path)

"""Provision the source/dest objects and a global access-group on the ASA."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e._sync import wait_for_synced
from sccfm_cli.e2e.access_rules.phases.test_data import (
    ASA_TEST_QUERY,
    TEST_ACL_NAME,
    TEST_DESTINATION_NETWORK,
    TEST_DESTINATION_VALUE,
    TEST_SOURCE_NETWORK,
    TEST_SOURCE_VALUE,
)


def run(ctx: ProfileContext) -> None:
    # Source / destination network objects.  Tolerate "already exists"
    # so a partial prior run doesn't block this one.
    for name, value, description in (
        (TEST_SOURCE_NETWORK, TEST_SOURCE_VALUE, "CI E2E source host for access rule tests"),
        (
            TEST_DESTINATION_NETWORK,
            TEST_DESTINATION_VALUE,
            "CI E2E destination host for access rule tests",
        ),
    ):
        run_cli(
            "objects",
            "network",
            "create",
            "--name",
            name,
            "--value",
            value,
            "--description",
            description,
            "--format",
            "json",
            profile=ctx.profile,
            config_path=ctx.config_path,
            tolerate_any_rc=True,
        )

    # Provision a global access-group via ASA CLI.  This must succeed —
    # the read/CRUD phases assume the ACL exists.  Wait for SYNCED first,
    # since the Ansible suite that ran before us may have left the device
    # mid-sync, and the API rejects script pushes against NOT_SYNCED devices.
    wait_for_synced(ctx, query=ASA_TEST_QUERY)

    provisioning_script = "\n".join(
        [
            "configure terminal",
            f"access-list {TEST_ACL_NAME} extended permit ip any any",
            f"access-group {TEST_ACL_NAME} global",
            "end",
        ]
    )
    run_cli(
        "inventory",
        "devices",
        "asa",
        "cli",
        "execute",
        "--query",
        ASA_TEST_QUERY,
        "--script",
        provisioning_script,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )

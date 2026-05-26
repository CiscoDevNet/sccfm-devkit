"""Re-run the same updates: PUT is idempotent at the API level so rc=0."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e.objects.phases.test_data import (
    TEST_OBJECTS,
    UPDATED_HOST_DESCRIPTION,
    UPDATED_HOST_VALUE,
    UPDATED_SUBNET_LABELS,
)


def run(ctx: ProfileContext) -> None:
    host = TEST_OBJECTS[0]
    subnet = TEST_OBJECTS[1]

    run_cli(
        "objects",
        "network",
        "update",
        "--name",
        host.name,
        "--value",
        UPDATED_HOST_VALUE,
        "--description",
        UPDATED_HOST_DESCRIPTION,
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )

    subnet_args = ["objects", "network", "update", "--name", subnet.name]
    for label in UPDATED_SUBNET_LABELS:
        subnet_args += ["--labels", label]
    subnet_args += ["--format", "json"]
    run_cli(*subnet_args, profile=ctx.profile, config_path=ctx.config_path)

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Update host literal+description and subnet labels."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.objects.phases.test_data import (
    TEST_OBJECTS,
    UPDATED_HOST_DESCRIPTION,
    UPDATED_HOST_VALUE,
    UPDATED_SUBNET_LABELS,
)


def run(ctx: ProfileContext) -> None:
    host = TEST_OBJECTS[0]
    subnet = TEST_OBJECTS[1]

    host_result = run_cli(
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
    payload = get_json(host_result)
    assert (
        payload.get("literal") == UPDATED_HOST_VALUE
    ), f"Expected host literal to update to {UPDATED_HOST_VALUE!r}, got {payload!r}"

    subnet_args = ["objects", "network", "update", "--name", subnet.name]
    for label in UPDATED_SUBNET_LABELS:
        subnet_args += ["--labels", label]
    subnet_args += ["--format", "json"]

    run_cli(*subnet_args, profile=ctx.profile, config_path=ctx.config_path)

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Create the test network objects."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import get_json, run_cli
from cisco_sccfm_cli.e2e.objects.phases.test_data import (
    OBJECT_LABELS,
    OBJECT_TAGS,
    TEST_OBJECTS,
)


def run(ctx: ProfileContext) -> None:
    for fixture in TEST_OBJECTS:
        args = [
            "objects",
            "network",
            "create",
            "--name",
            fixture.name,
            "--value",
            fixture.value,
            "--description",
            fixture.description,
        ]
        for label in OBJECT_LABELS:
            args += ["--labels", label]
        for tag in OBJECT_TAGS:
            args += ["--tags", tag]
        args += ["--format", "json"]

        result = run_cli(*args, profile=ctx.profile, config_path=ctx.config_path)
        payload = get_json(result)
        assert (
            payload.get("name") == fixture.name
        ), f"Created object name mismatch: {payload.get('name')!r} != {fixture.name!r}"
        assert (
            payload.get("literal") == fixture.value
        ), f"Created object literal mismatch: {payload.get('literal')!r} != {fixture.value!r}"

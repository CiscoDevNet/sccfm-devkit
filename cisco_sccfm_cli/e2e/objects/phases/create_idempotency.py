# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Re-create the same objects: the CLI must reject with non-zero rc."""

from __future__ import annotations

from cisco_sccfm_cli.e2e._profile import ProfileContext
from cisco_sccfm_cli.e2e._runner import run_cli
from cisco_sccfm_cli.e2e.objects.phases.test_data import OBJECT_LABELS, OBJECT_TAGS, TEST_OBJECTS


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

        run_cli(
            *args,
            profile=ctx.profile,
            config_path=ctx.config_path,
            expect_failure=True,
            expected_error=("already exists", "conflict"),
            parse_json=False,
        )

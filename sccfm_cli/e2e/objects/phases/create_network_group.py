# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Create the test network group with literal members."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.objects.phases.test_data import (
    OBJECT_LABELS,
    OBJECT_TAGS,
    TEST_GROUP_DESCRIPTION,
    TEST_GROUP_LITERALS,
    TEST_GROUP_NAME,
)


def run(ctx: ProfileContext) -> None:
    args = ["objects", "network-group", "create", "--name", TEST_GROUP_NAME]
    for literal in TEST_GROUP_LITERALS:
        args += ["--network-literal", literal]
    args += ["--description", TEST_GROUP_DESCRIPTION]
    for label in OBJECT_LABELS:
        args += ["--labels", label]
    for tag in OBJECT_TAGS:
        args += ["--tags", tag]
    args += ["--format", "json"]

    result = run_cli(*args, profile=ctx.profile, config_path=ctx.config_path)
    payload = get_json(result)
    assert (
        payload.get("name") == TEST_GROUP_NAME
    ), f"Created group name mismatch: {payload.get('name')!r} != {TEST_GROUP_NAME!r}"
    literals = payload.get("literals") or []
    assert len(literals) == len(
        TEST_GROUP_LITERALS
    ), f"Expected {len(TEST_GROUP_LITERALS)} literals, got {literals!r}"

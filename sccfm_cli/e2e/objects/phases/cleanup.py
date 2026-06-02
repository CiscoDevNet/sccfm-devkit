# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Pre/post-test cleanup: tolerate missing resources on a fresh tenant."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e.objects.phases.test_data import (
    TEST_GROUP_NAME,
    TEST_OBJECT_NAMES,
)


def run(ctx: ProfileContext) -> None:
    # Group must come down before the underlying objects.
    run_cli(
        "objects",
        "network-group",
        "delete",
        "--name",
        TEST_GROUP_NAME,
        profile=ctx.profile,
        config_path=ctx.config_path,
        tolerate_any_rc=True,
        parse_json=False,
    )

    for name in TEST_OBJECT_NAMES:
        run_cli(
            "objects",
            "network",
            "delete",
            "--name",
            name,
            profile=ctx.profile,
            config_path=ctx.config_path,
            tolerate_any_rc=True,
            parse_json=False,
        )

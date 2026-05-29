# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Delete the test network objects."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import run_cli
from sccfm_cli.e2e.objects.phases.test_data import TEST_OBJECT_NAMES


def run(ctx: ProfileContext) -> None:
    for name in TEST_OBJECT_NAMES:
        run_cli(
            "objects",
            "network",
            "delete",
            "--name",
            name,
            profile=ctx.profile,
            config_path=ctx.config_path,
            parse_json=False,
        )

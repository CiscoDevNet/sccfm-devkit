# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from click.testing import CliRunner

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.models import Config

POSIX_ONLY = pytest.mark.skipif(
    os.name != "posix",
    reason="POSIX permission bits are not portable to this platform",
)


@POSIX_ONLY
def test_status_rejects_unsafe_profile_without_changing_permissions(
    cli_runner: CliRunner,
    default_config: Config,
    config_path: Path,
) -> None:
    """Readonly profile checks must fail closed without repairing local metadata."""
    config_path.chmod(0o644)
    parent_mode = stat.S_IMODE(config_path.parent.stat().st_mode)

    result = cli_runner.invoke(cli, ["status"])

    assert result.exit_code != 0
    assert "expected 0600, found 0644" in result.output
    assert "sccfm-cli configure" in result.output
    assert default_config.api_token not in result.output
    assert default_config.api_token not in repr(result.exception)
    assert stat.S_IMODE(config_path.stat().st_mode) == 0o644
    assert stat.S_IMODE(config_path.parent.stat().st_mode) == parent_mode

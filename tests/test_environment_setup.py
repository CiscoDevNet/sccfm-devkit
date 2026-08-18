# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for project environment setup scripts."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPTS = (
    PROJECT_ROOT / "cisco_sccfm_scripts" / "setup_ci_environment.sh",
    PROJECT_ROOT / "cisco_sccfm_scripts" / "setup_environment.sh",
)
POETRY_GROUP_ARGUMENT = re.compile(
    r"\binstall --with (?P<groups>[A-Za-z0-9_-]+(?:,[A-Za-z0-9_-]+)*)"
)


def _defined_poetry_groups() -> set[str]:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as file_handle:
        pyproject: dict[str, object] = tomllib.load(file_handle)

    tool = pyproject["tool"]
    assert isinstance(tool, dict)
    poetry = tool["poetry"]
    assert isinstance(poetry, dict)
    groups = poetry["group"]
    assert isinstance(groups, dict)
    return {str(group) for group in groups}


def test_setup_scripts_request_defined_poetry_groups() -> None:
    defined_groups = _defined_poetry_groups()

    for script in SETUP_SCRIPTS:
        source = script.read_text(encoding="utf-8")
        matches = list(POETRY_GROUP_ARGUMENT.finditer(source))
        assert matches, f"{script.name} does not install a Poetry dependency group"

        for match in matches:
            requested_groups = set(match.group("groups").split(","))
            assert requested_groups <= defined_groups, (
                f"{script.name} requests undefined Poetry groups: "
                f"{sorted(requested_groups - defined_groups)}"
            )

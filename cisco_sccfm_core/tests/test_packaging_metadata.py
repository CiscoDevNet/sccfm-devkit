# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the published Python package metadata."""

import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _poetry_config() -> dict[str, Any]:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)
    return dict(pyproject["tool"]["poetry"])


def test_distribution_uses_cisco_devkit_name() -> None:
    assert _poetry_config()["name"] == "cisco-sccfm-devkit"


def test_published_packages_use_cisco_prefix() -> None:
    poetry = _poetry_config()
    included_packages = {package["include"] for package in poetry["packages"]}
    script_targets = set(poetry["scripts"].values())

    assert included_packages == {
        "cisco_sccfm_cli",
        "cisco_sccfm_core",
        "cisco_sccfm_scripts",
    }
    assert script_targets
    assert all(target.startswith("cisco_sccfm_") for target in script_targets)

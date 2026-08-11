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


def test_published_package_contract_is_cli_and_core_only() -> None:
    poetry = _poetry_config()
    included_packages = {package["include"] for package in poetry["packages"]}

    assert included_packages == {
        "cisco_sccfm_cli",
        "cisco_sccfm_core",
    }
    assert poetry["scripts"] == {"sccfm-cli": "cisco_sccfm_cli.cli:cli"}


def test_published_packages_exclude_repository_only_code() -> None:
    assert set(_poetry_config()["exclude"]) == {
        "cisco_sccfm_scripts",
        "**/tests",
        "**/e2e",
        "**/__pycache__",
        "**/.pytest_cache",
        "**/.mypy_cache",
        "**/*.pyc",
        "**/*.pyo",
        "**/.DS_Store",
    }


def test_generated_sdk_is_pinned_to_the_verified_compatible_version() -> None:
    poetry = _poetry_config()
    collection_requirements = (PROJECT_ROOT / "sccfm-ansible" / "requirements.txt").read_text(
        encoding="utf-8"
    )

    assert poetry["dependencies"]["scc-firewall-manager-sdk"] == "1.17.27"
    assert "scc-firewall-manager-sdk==1.17.27" in collection_requirements.splitlines()


def test_pyinstaller_spec_uses_repository_relative_entrypoint() -> None:
    spec = (PROJECT_ROOT / "sccfm-cli.spec").read_text(encoding="utf-8")

    assert "['cisco_sccfm_cli/cli.py']" in spec
    assert "/Users/" not in spec

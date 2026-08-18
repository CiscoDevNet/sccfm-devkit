# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the published Python package metadata."""

from __future__ import annotations

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


def test_interactive_entrypoint_is_completely_renamed() -> None:
    scripts = _poetry_config()["scripts"]

    assert scripts["sccfm-cli-interactive"] == "cisco_sccfm_scripts.interactive_cli:main"
    assert "devkit" not in scripts
    assert "change-tokens" not in scripts


def test_user_guidance_only_references_canonical_profile_configuration() -> None:
    guidance_paths = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "INSTALL.md",
        PROJECT_ROOT / "CONTRIBUTING.md",
        PROJECT_ROOT / "sccfm-ansible" / "README.md",
        PROJECT_ROOT / "skills" / "sccfm-cli" / "SKILL.md",
        PROJECT_ROOT / "skills" / "sccfm-ansible" / "SKILL.md",
    ]

    for path in guidance_paths:
        guidance = path.read_text(encoding="utf-8")
        assert "change-tokens" not in guidance, path
        assert "`devkit`" not in guidance, path
        assert "SCCFM_API_TOKEN" not in guidance, path
        assert "SCCFM_REGION" not in guidance, path
        assert ".env.example" not in guidance, path


def test_pyinstaller_spec_uses_repository_relative_entrypoint() -> None:
    spec = (PROJECT_ROOT / "sccfm-cli.spec").read_text(encoding="utf-8")

    assert "['cisco_sccfm_cli/cli.py']" in spec
    assert "/Users/" not in spec

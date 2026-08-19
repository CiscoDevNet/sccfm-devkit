# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the published Python package metadata."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _pyproject() -> dict[str, Any]:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as pyproject_file:
        return tomllib.load(pyproject_file)


def _project_config() -> dict[str, Any]:
    return dict(_pyproject()["project"])


def _poetry_config() -> dict[str, Any]:
    return dict(_pyproject()["tool"]["poetry"])


def test_distribution_uses_cisco_devkit_name() -> None:
    assert _project_config()["name"] == "cisco-sccfm-devkit"


def test_published_package_contract_is_cli_and_core_only() -> None:
    poetry = _poetry_config()
    included_packages = {package["include"] for package in poetry["packages"]}

    assert included_packages == {
        "cisco_sccfm_cli",
        "cisco_sccfm_core",
    }
    assert _project_config()["scripts"] == {
        "sccfm-cli": "cisco_sccfm_cli.cli:cli",
        "sccfm-cli-interactive": "cisco_sccfm_cli.interactive:main",
    }


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
    assert "scc-firewall-manager-sdk==1.17.27" in _project_config()["dependencies"]


def test_interactive_entrypoint_is_published_from_the_cli_package() -> None:
    scripts = _project_config()["scripts"]

    assert scripts["sccfm-cli-interactive"] == "cisco_sccfm_cli.interactive:main"


def test_interactive_prompt_dependency_is_installed_for_users() -> None:
    pyproject = _pyproject()

    assert "questionary>=2.1.1,<3" in _project_config()["dependencies"]
    assert "questionary" not in pyproject["tool"]["poetry"]["group"]["dev"]["dependencies"]


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
        if path != PROJECT_ROOT / "README.md":
            assert "SCCFM_API_TOKEN" not in guidance, path
        assert "SCCFM_REGION" not in guidance, path
        assert ".env.example" not in guidance, path

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.count("SCCFM_API_TOKEN") == 1
    assert "interactive hidden prompt" in readme
    assert "can expose the token in shell history and process listings" in readme


def test_pyinstaller_spec_uses_repository_relative_entrypoint() -> None:
    spec = (PROJECT_ROOT / "sccfm-cli.spec").read_text(encoding="utf-8")

    assert "['cisco_sccfm_cli/cli.py']" in spec
    assert "/Users/" not in spec

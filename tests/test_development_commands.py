# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the local-only maintainer command distribution."""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from importlib.metadata import distribution
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEVTOOLS_PYPROJECT = PROJECT_ROOT / "devtools" / "pyproject.toml"
COMMAND_MODULES = {
    "build-ansible-collection": "cisco_sccfm_scripts.build_ansible_collection:main",
    "change-tokens": "cisco_sccfm_scripts.setup_tokens:main",
    "check-doc-artifacts": "cisco_sccfm_scripts.check_doc_artifacts:main",
    "check-doc-links": "cisco_sccfm_scripts.check_doc_links:main",
    "devkit": "cisco_sccfm_scripts.devkit_cli:main",
    "generate-ansible-docs": "cisco_sccfm_scripts.generate_ansible_docs:main",
    "generate-cli-docs": "cisco_sccfm_scripts.generate_cli_docs:main",
    "generate-cli-man-docs": "cisco_sccfm_scripts.generate_cli_man_docs:main",
    "install-cli-man-docs": "cisco_sccfm_scripts.install_cli_man_docs:main",
    "sync-docs-readme": "cisco_sccfm_scripts.sync_docs_readme:main",
}
DOCUMENTATION_COMMANDS = (
    "sync-docs-readme",
    "generate-cli-docs",
    "generate-cli-man-docs",
    "generate-ansible-docs",
)


def _load_pyproject(path: Path) -> dict[str, object]:
    with path.open("rb") as file_handle:
        return tomllib.load(file_handle)


def test_devtools_declares_exact_maintainer_commands() -> None:
    pyproject = _load_pyproject(DEVTOOLS_PYPROJECT)
    project = pyproject["project"]

    assert isinstance(project, dict)
    assert project["name"] == "cisco-sccfm-devtools"
    assert project["scripts"] == COMMAND_MODULES


def test_root_declares_devtools_only_as_a_development_dependency() -> None:
    pyproject = _load_pyproject(PROJECT_ROOT / "pyproject.toml")
    tool = pyproject["tool"]
    project = pyproject["project"]

    assert isinstance(tool, dict)
    assert isinstance(project, dict)
    poetry = tool["poetry"]
    assert isinstance(poetry, dict)
    dependencies = poetry["group"]["dev"]["dependencies"]
    assert dependencies["cisco-sccfm-devtools"] == {
        "path": "devtools",
        "develop": True,
    }
    assert all(
        not dependency.startswith("cisco-sccfm-devtools") for dependency in project["dependencies"]
    )


def test_installed_devtools_entry_points_match_and_load() -> None:
    console_scripts = {
        entry_point.name: entry_point
        for entry_point in distribution("cisco-sccfm-devtools").entry_points
        if entry_point.group == "console_scripts"
    }

    assert {name: entry_point.value for name, entry_point in console_scripts.items()} == (
        COMMAND_MODULES
    )
    assert all(callable(entry_point.load()) for entry_point in console_scripts.values())


def test_requested_poetry_run_commands_work_without_activation() -> None:
    poetry = shutil.which("poetry")
    assert poetry is not None

    for command in DOCUMENTATION_COMMANDS:
        result = subprocess.run(
            [poetry, "run", command, "--help"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr

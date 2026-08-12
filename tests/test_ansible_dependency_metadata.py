# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any, cast

import yaml

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_COLLECTION_ROOT = _REPOSITORY_ROOT / "sccfm-ansible"


def _yaml_mapping(path: Path) -> dict[str, Any]:
    """Load a YAML mapping from a collection metadata file."""
    document = yaml.safe_load(path.read_text())
    assert isinstance(document, dict)
    return cast(dict[str, Any], document)


def test_collection_python_requirement_matches_release_versions() -> None:
    """Require the collection and its Python runtime package to ship in lockstep."""
    pyproject = tomllib.loads((_REPOSITORY_ROOT / "pyproject.toml").read_text())
    project_version = pyproject["project"]["version"]
    galaxy_version = _yaml_mapping(_COLLECTION_ROOT / "galaxy.yml")["version"]
    requirement_lines = [
        line.strip()
        for line in (_COLLECTION_ROOT / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    dependency_source = (
        _COLLECTION_ROOT / "plugins" / "module_utils" / "dependencies.py"
    ).read_text()
    runtime_requirement = re.search(
        r'^_PAIRED_DEVKIT_REQUIREMENT = "(?P<requirement>[^"]+)"$',
        dependency_source,
        re.MULTILINE,
    )

    assert galaxy_version == project_version
    assert requirement_lines == [f"cisco-sccfm-devkit=={project_version}"]
    assert runtime_requirement is not None
    assert runtime_requirement.group("requirement") == requirement_lines[0]


def test_execution_environment_uses_collection_requirements() -> None:
    """Point Ansible Builder at the version-matched controller requirement."""
    metadata = _yaml_mapping(_COLLECTION_ROOT / "meta" / "execution-environment.yml")

    assert metadata == {"dependencies": {"python": "requirements.txt"}}


def test_supported_ansible_range_matches_development_and_collection_metadata() -> None:
    """Keep the tested controller range consistent with the published collection."""
    pyproject = tomllib.loads((_REPOSITORY_ROOT / "pyproject.toml").read_text())
    runtime = _yaml_mapping(_COLLECTION_ROOT / "meta" / "runtime.yml")

    assert pyproject["tool"]["poetry"]["group"]["dev"]["dependencies"]["ansible-core"] == (
        ">=2.20,<2.22"
    )
    assert runtime["requires_ansible"] == ">=2.20.0,<2.22.0"


def test_runtime_metadata_excludes_unsupported_module_defaults() -> None:
    """Keep module defaults in playbooks, not unsupported runtime metadata."""
    runtime = _yaml_mapping(_COLLECTION_ROOT / "meta" / "runtime.yml")

    assert "module_defaults" not in runtime
    assert "cisco.sccfm.all" in runtime["action_groups"]


def test_galaxy_metadata_describes_the_published_collection() -> None:
    """Describe both public plugin types and use one unambiguous license source."""
    galaxy = _yaml_mapping(_COLLECTION_ROOT / "galaxy.yml")
    description = galaxy["description"].lower()

    assert "modules" in description
    assert "inventory" in description
    assert galaxy["license_file"] == "LICENSE"
    assert "license" not in galaxy


def test_collection_changelog_matches_published_version() -> None:
    """Keep Galaxy metadata and both generated changelog forms version-aligned."""
    galaxy = _yaml_mapping(_COLLECTION_ROOT / "galaxy.yml")
    changelog = _yaml_mapping(_COLLECTION_ROOT / "changelogs" / "changelog.yaml")
    changelog_config = _yaml_mapping(_COLLECTION_ROOT / "changelogs" / "config.yaml")
    version = str(galaxy["version"])

    assert changelog_config["changes_file"] == "changelog.yaml"
    assert changelog_config["notesdir"] == "fragments"
    assert version in changelog["releases"]
    assert f"v{version}" in (_COLLECTION_ROOT / "CHANGELOG.rst").read_text()

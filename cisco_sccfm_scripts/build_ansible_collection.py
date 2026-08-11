#!/usr/bin/env python3

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Build script for Ansible collection."""
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

from cisco_sccfm_scripts.verify_ansible_collection import (
    ArtifactVerificationError,
    verify_collection_artifact,
)

_PAIRED_REQUIREMENT_PIN = re.compile(
    r"^[ \t]*cisco-sccfm-devkit[ \t]*==[ \t]*[^\s;#]+[ \t]*(?:#.*)?" r"(?P<newline>\r?\n)?$",
    re.IGNORECASE,
)


class CollectionBuildError(RuntimeError):
    """Raised when collection source cannot be prepared safely for a build."""


def _find_collection_symlink(collection_dir: Path) -> Path | None:
    """Return the first symlink without following targets outside the collection."""
    for root, directories, files in os.walk(collection_dir, followlinks=False):
        for name in sorted([*directories, *files]):
            candidate = Path(root) / name
            if candidate.is_symlink():
                return candidate.relative_to(collection_dir)
    return None


def _sync_paired_python_requirement(requirements_path: Path, version: str) -> None:
    """Synchronize the sole active requirement, which must be an exact devkit pin."""
    content = requirements_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    active_requirements = [
        (index, line)
        for index, line in enumerate(lines)
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(active_requirements) != 1:
        raise CollectionBuildError(
            "requirements.txt must contain only one cisco-sccfm-devkit requirement"
        )

    index, requirement = active_requirements[0]
    match = _PAIRED_REQUIREMENT_PIN.fullmatch(requirement)
    if match is None:
        raise CollectionBuildError(
            "cisco-sccfm-devkit must use one exact == version pin in requirements.txt"
        )

    lines[index] = f"cisco-sccfm-devkit=={version}{match.group('newline') or ''}"
    updated = "".join(lines)
    if updated != content:
        requirements_path.write_text(updated, encoding="utf-8")


def main() -> int:
    """Build the Ansible collection tarball."""
    project_root = Path(__file__).parent.parent
    collection_dir = project_root / "sccfm-ansible"
    dist_dir = project_root / "dist"
    pyproject_path = project_root / "pyproject.toml"
    galaxy_path = collection_dir / "galaxy.yml"
    requirements_path = collection_dir / "requirements.txt"
    license_src = project_root / "LICENSE"
    license_dst = collection_dir / "LICENSE"

    print("🎭 Building Ansible collection...")

    symlink = _find_collection_symlink(collection_dir)
    if symlink is not None:
        print(f"❌ Collection source contains a symlink: {symlink}", file=sys.stderr)
        return 1

    # Read version from pyproject.toml
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    version = pyproject["tool"]["poetry"]["version"]
    print(f"📦 Using version {version} from pyproject.toml")

    try:
        _sync_paired_python_requirement(requirements_path, version)
    except (CollectionBuildError, OSError) as exc:
        print(f"❌ Failed to synchronize Python requirements: {exc}", file=sys.stderr)
        return 1
    print(f"✏️  Synchronized cisco-sccfm-devkit requirement to {version}")

    # Include the declared Apache license after all fail-closed source validation.
    shutil.copyfile(license_src, license_dst)
    print(f"📄 Copied LICENSE into {collection_dir.name}/")

    # Update galaxy.yml with the version
    with open(galaxy_path, "r") as f:
        galaxy = yaml.safe_load(f)

    galaxy["version"] = version

    with open(galaxy_path, "w") as f:
        yaml.dump(galaxy, f, default_flow_style=False, sort_keys=False)

    print(f"✏️  Updated galaxy.yml with version {version}")

    # Ensure dist directory exists
    dist_dir.mkdir(exist_ok=True)

    # Build the collection
    result = subprocess.run(
        ["ansible-galaxy", "collection", "build", "--output-path", str(dist_dir), "--force"],
        cwd=collection_dir,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"❌ Failed to build Ansible collection:\n{result.stderr}", file=sys.stderr)
        return 1

    artifact_path = dist_dir / f"cisco-sccfm-{version}.tar.gz"
    try:
        verification = verify_collection_artifact(artifact_path, expected_version=version)
    except ArtifactVerificationError as exc:
        artifact_path.unlink(missing_ok=True)
        print(f"❌ Collection artifact rejected: {exc}", file=sys.stderr)
        return 1

    print("✅ Ansible collection built and verified successfully")
    print(f"🔐 SHA-256: {verification.sha256}")
    print(result.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())

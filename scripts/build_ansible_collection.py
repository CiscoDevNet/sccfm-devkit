#!/usr/bin/env python3
"""Build script for Ansible collection."""
import subprocess
import sys
from pathlib import Path

import tomli
import yaml


def main() -> int:
    """Build the Ansible collection tarball."""
    project_root = Path(__file__).parent.parent
    collection_dir = project_root / "sccfm-ansible"
    dist_dir = project_root / "dist"
    pyproject_path = project_root / "pyproject.toml"
    galaxy_path = collection_dir / "galaxy.yml"

    print("🎭 Building Ansible collection...")

    # Read version from pyproject.toml
    with open(pyproject_path, "rb") as f:
        pyproject = tomli.load(f)
    version = pyproject["tool"]["poetry"]["version"]
    print(f"📦 Using version {version} from pyproject.toml")

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

    print("✅ Ansible collection built successfully")
    print(result.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())

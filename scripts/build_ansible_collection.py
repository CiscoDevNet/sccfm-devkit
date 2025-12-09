#!/usr/bin/env python3
"""Build script for Ansible collection."""
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Build the Ansible collection tarball."""
    project_root = Path(__file__).parent.parent
    collection_dir = project_root / "sccfm-ansible"
    dist_dir = project_root / "dist"

    print("🎭 Building Ansible collection...")

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

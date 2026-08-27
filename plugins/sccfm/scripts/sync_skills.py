#!/usr/bin/env python3
# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Synchronize the plugin's distributed skills with the repository sources."""

from __future__ import annotations

import argparse
import filecmp
import shutil
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLUGIN_ROOT.parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "skills"
TARGET_ROOT = PLUGIN_ROOT / "skills"
SKILLS = ("sccfm-cli", "sccfm-ansible")


def skill_matches(name: str) -> bool:
    source = SOURCE_ROOT / name
    target = TARGET_ROOT / name
    comparison = filecmp.dircmp(source, target)
    return not (
        comparison.left_only
        or comparison.right_only
        or comparison.diff_files
        or comparison.funny_files
        or any(not child.same_files for child in comparison.subdirs.values())
    )


def synchronize() -> None:
    TARGET_ROOT.mkdir(parents=True, exist_ok=True)
    for name in SKILLS:
        source = SOURCE_ROOT / name
        target = TARGET_ROOT / name
        if not source.is_dir():
            raise SystemExit(f"Missing canonical skill: {source}")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        print(f"Synchronized {name}")


def check() -> None:
    stale = [name for name in SKILLS if not skill_matches(name)]
    if stale:
        raise SystemExit("Plugin skills are stale: " + ", ".join(stale))
    print("Plugin skills match canonical sources")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    if arguments.check:
        check()
    else:
        synchronize()


if __name__ == "__main__":
    main()

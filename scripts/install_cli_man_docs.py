#!/usr/bin/env python3

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Install generated sccfm-cli manual pages into a local man directory."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from scripts import generate_cli_man_docs


class ManPageInstallError(RuntimeError):
    """Raised when generated manual pages cannot be installed."""


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_man_root() -> Path:
    """Return the default user-level man root."""
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    data_home = Path(xdg_data_home).expanduser() if xdg_data_home else Path.home() / ".local/share"
    return data_home / "man"


def _resolve_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _generated_man_pages(source_dir: Path) -> list[Path]:
    pages = sorted(source_dir.glob("sccfm-cli*.1"))
    if not pages:
        raise ManPageInstallError(f"No generated sccfm-cli man pages found in {source_dir}.")
    return pages


def install_man_pages(source_dir: Path, man_root: Path) -> int:
    """Replace installed sccfm-cli man pages with generated pages."""
    pages = _generated_man_pages(source_dir)
    target_dir = man_root / "man1"
    target_dir.mkdir(parents=True, exist_ok=True)

    for stale_page in target_dir.glob("sccfm-cli*.1"):
        if stale_page.is_dir() and not stale_page.is_symlink():
            raise ManPageInstallError(f"Refusing to remove non-file path {stale_page}.")
        stale_page.unlink()

    for page in pages:
        shutil.copy2(page, target_dir / page.name)
    return len(pages)


def current_manpath() -> list[Path]:
    """Return the current man search path, if the platform exposes one."""
    if shutil.which("manpath"):
        result = subprocess.run(
            ["manpath"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return [
                Path(entry).expanduser()
                for entry in result.stdout.strip().split(os.pathsep)
                if entry
            ]

    manpath_env = os.environ.get("MANPATH", "")
    return [Path(entry).expanduser() for entry in manpath_env.split(os.pathsep) if entry]


def man_root_in_manpath(man_root: Path, manpath_entries: Sequence[Path]) -> bool:
    resolved_man_root = _resolve_path(man_root)
    return any(_resolve_path(entry) == resolved_man_root for entry in manpath_entries)


def _verification_env(man_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    existing_manpath = env.get("MANPATH")
    env["MANPATH"] = (
        f"{man_root}{os.pathsep}{existing_manpath}" if existing_manpath else str(man_root)
    )
    return env


def verify_man_page(man_root: Path) -> str | None:
    """Verify that man can find sccfm-cli when pointed at the install root."""
    if not shutil.which("man"):
        return None

    result = subprocess.run(
        ["man", "-w", "sccfm-cli"],
        env=_verification_env(man_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise ManPageInstallError(f"man could not find sccfm-cli: {details}")
    return result.stdout.strip()


def _format_export(man_root: Path) -> str:
    home = Path.home().resolve(strict=False)
    resolved = _resolve_path(man_root)
    try:
        display = f"$HOME/{resolved.relative_to(home)}"
    except ValueError:
        display = str(resolved)
    return f'export MANPATH="{display}:$MANPATH"'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install generated sccfm-cli manual pages.")
    parser.add_argument(
        "--prefix",
        type=Path,
        default=default_man_root(),
        help="Man root directory that contains or will contain man1/.",
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=generate_cli_man_docs.DEFAULT_OUTPUT_DIR,
        help="Directory containing generated .1 files.",
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Install existing generated pages without regenerating them first.",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip verification with man -w.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = _project_root()
    docs_dir = args.docs_dir if args.docs_dir.is_absolute() else project_root / args.docs_dir
    man_root = _resolve_path(args.prefix)

    if not args.skip_generate:
        rc = generate_cli_man_docs.main(["--output-dir", str(docs_dir)])
        if rc:
            return rc

    try:
        installed = install_man_pages(docs_dir, man_root)
        print(f"Installed {installed} CLI man pages into {man_root / 'man1'}")
        if not args.no_verify:
            verified_path = verify_man_page(man_root)
            if verified_path is None:
                print("Skipped verification: man is not available on this system.")
            else:
                print(f"Verified sccfm-cli man page: {verified_path}")
    except ManPageInstallError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not man_root_in_manpath(man_root, current_manpath()):
        print("The install directory is not currently in manpath.")
        print("Add this to your shell startup file if bare `man sccfm-cli` does not work:")
        print(f"  {_format_export(man_root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

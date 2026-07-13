#!/usr/bin/env python3

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Generate CLI manual pages from the Click command tree."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping, Sequence

from click_man.core import write_man_pages

from cisco_sccfm_cli.cli import cli

DEFAULT_OUTPUT_DIR = Path("docs/man/man1")
STABLE_FALLBACK_SOURCE_DATE_EPOCH = "946684800"
PARAGRAPH_AFTER_SECTION_RE = re.compile(r"(?m)(^\.SH .+\n)\.PP\n")


class OutputDirectoryError(ValueError):
    """Raised when an output directory cannot be safely replaced."""


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _project_version(project_root: Path) -> str:
    with (project_root / "pyproject.toml").open("rb") as pyproject:
        data = tomllib.load(pyproject)
    version = data["tool"]["poetry"]["version"]
    if not isinstance(version, str):
        raise RuntimeError("Project version in pyproject.toml must be a string.")
    return version


def _source_date_epoch(project_root: Path) -> str:
    if source_date_epoch := os.environ.get("SOURCE_DATE_EPOCH"):
        return source_date_epoch

    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "-1",
                "--format=%ct",
                "--",
                "pyproject.toml",
                "cisco_sccfm_cli",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return STABLE_FALLBACK_SOURCE_DATE_EPOCH
    epoch = result.stdout.strip()
    if result.returncode == 0 and epoch.isdigit():
        return epoch
    return STABLE_FALLBACK_SOURCE_DATE_EPOCH


@contextmanager
def _source_date_environment(source_date_epoch: str) -> Iterator[None]:
    previous = os.environ.get("SOURCE_DATE_EPOCH")
    os.environ["SOURCE_DATE_EPOCH"] = source_date_epoch
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("SOURCE_DATE_EPOCH", None)
        else:
            os.environ["SOURCE_DATE_EPOCH"] = previous


def _validate_output_directory(docs_root: Path, default_docs_root: Path) -> None:
    if not docs_root.exists():
        return
    if not docs_root.is_dir() or docs_root.is_symlink():
        raise OutputDirectoryError(f"Refusing to overwrite non-directory path {docs_root}.")
    if docs_root.resolve() == default_docs_root.resolve():
        return
    if any(docs_root.iterdir()):
        raise OutputDirectoryError(
            f"Refusing to overwrite non-empty custom output directory {docs_root}. "
            "Use the default output directory or choose an empty path."
        )


def _write_files(files: Mapping[Path, str], docs_root: Path, default_docs_root: Path) -> None:
    _validate_output_directory(docs_root, default_docs_root)
    if docs_root.exists():
        shutil.rmtree(docs_root)
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _generate_files(project_root: Path, docs_root: Path) -> Mapping[Path, str]:
    version = _project_version(project_root)
    source_date_epoch = _source_date_epoch(project_root)

    with tempfile.TemporaryDirectory() as tmp:
        scratch_root = Path(tmp)
        with _source_date_environment(source_date_epoch):
            write_man_pages(
                "sccfm-cli",
                cli,
                version=version,
                target_dir=str(scratch_root),
            )
        return {
            docs_root / path.name: _clean_man_page(path.read_text(encoding="utf-8"))
            for path in sorted(scratch_root.glob("*.1"))
        }


def _clean_man_page(content: str) -> str:
    return PARAGRAPH_AFTER_SECTION_RE.sub(r"\1", content)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate CLI manual pages.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate that manual pages can be generated without writing files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for generated CLI manual pages.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = _project_root()
    docs_root = args.output_dir if args.output_dir.is_absolute() else project_root / args.output_dir
    default_docs_root = project_root / DEFAULT_OUTPUT_DIR
    files = _generate_files(project_root, docs_root)

    if args.check:
        print(f"Generated {len(files)} CLI manual pages in memory")
    else:
        try:
            _write_files(files, docs_root, default_docs_root)
        except OutputDirectoryError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"Generated {len(files)} CLI manual pages in {docs_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

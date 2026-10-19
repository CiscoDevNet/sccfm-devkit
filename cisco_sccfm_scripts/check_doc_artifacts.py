#!/usr/bin/env python3

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Check generated documentation artifacts for terminal/control-character leaks."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_DOCS_ROOT = Path("docs")
TEXT_SUFFIXES = frozenset({".md", ".1"})
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


@dataclass(frozen=True)
class DocArtifactIssue:
    path: Path
    description: str
    line: int | None = None
    column: int | None = None


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _text_artifacts(docs_root: Path) -> Iterable[Path]:
    if not docs_root.exists():
        return []
    return sorted(
        path for path in docs_root.rglob("*") if path.is_file() and path.suffix in TEXT_SUFFIXES
    )


def _location(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    line_start = text.rfind("\n", 0, offset) + 1
    column = offset - line_start + 1
    return line, column


def _scan_text(path: Path, text: str) -> list[DocArtifactIssue]:
    issues: list[DocArtifactIssue] = []
    if match := ANSI_ESCAPE_RE.search(text):
        line, column = _location(text, match.start())
        issues.append(
            DocArtifactIssue(
                path=path,
                description="contains ANSI terminal escape sequence",
                line=line,
                column=column,
            )
        )
    replacement_offset = text.find("\ufffd")
    if replacement_offset != -1:
        line, column = _location(text, replacement_offset)
        issues.append(
            DocArtifactIssue(
                path=path,
                description="contains Unicode replacement character",
                line=line,
                column=column,
            )
        )
    return issues


def _scan_file(path: Path) -> list[DocArtifactIssue]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [
            DocArtifactIssue(
                path=path,
                description=f"is not valid UTF-8: {exc.reason}",
            )
        ]
    return _scan_text(path, text)


def check_docs(docs_root: Path) -> list[DocArtifactIssue]:
    issues: list[DocArtifactIssue] = []
    for path in _text_artifacts(docs_root):
        issues.extend(_scan_file(path))
    return issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check generated documentation artifacts.")
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=DEFAULT_DOCS_ROOT,
        help="Documentation root to scan.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = _project_root()
    docs_root = args.docs_root if args.docs_root.is_absolute() else project_root / args.docs_root
    issues = check_docs(docs_root)
    if issues:
        for issue in issues:
            location = ""
            if issue.line is not None and issue.column is not None:
                location = f":{issue.line}:{issue.column}"
            print(f"{issue.path}{location}: {issue.description}", file=sys.stderr)
        return 1

    print(f"Checked generated documentation artifacts under {docs_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

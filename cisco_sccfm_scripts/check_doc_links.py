#!/usr/bin/env python3

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Check internal Markdown links in generated documentation."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Sequence
from urllib.parse import unquote, urlparse

LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _is_external(target: str) -> bool:
    parsed = urlparse(target)
    return bool(parsed.scheme or parsed.netloc)


def _strip_fragment(target: str) -> str:
    return target.split("#", 1)[0]


def _candidate_paths(source: Path, target: str) -> list[Path]:
    path = source.parent / unquote(target)
    candidates = [path]
    if path.suffix == ".html":
        candidates.append(path.with_suffix(".md"))
    if path.is_dir():
        candidates.append(path / "index.md")
    return candidates


def _missing_links(docs_root: Path) -> list[str]:
    failures: list[str] = []
    for source in sorted(docs_root.rglob("*.md")):
        content = source.read_text(encoding="utf-8")
        for match in LINK_PATTERN.finditer(content):
            raw_target = match.group(1).strip()
            target = _strip_fragment(raw_target)
            if not target or _is_external(target):
                continue
            candidates = _candidate_paths(source, target)
            if not any(path.exists() for path in candidates):
                relative_source = source.relative_to(_project_root())
                failures.append(f"{relative_source}: missing link target {raw_target!r}")
    return failures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check internal documentation links.")
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path("docs"),
        help="Documentation root to check.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    docs_root = args.docs_root if args.docs_root.is_absolute() else _project_root() / args.docs_root
    failures = _missing_links(docs_root)
    if failures:
        print("Documentation link check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Checked internal links under {docs_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

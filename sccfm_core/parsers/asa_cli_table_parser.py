from __future__ import annotations

import re
from typing import Sequence


def normalize_cli_output(result_text: str | None) -> list[str]:
    """Normalize raw CLI output into non-empty lines."""
    if not result_text:
        return []
    output = result_text.replace("\\t", "\t")
    return [line.rstrip() for line in output.splitlines() if line.strip()]


def split_cli_columns(text: str) -> list[str]:
    """Split a CLI row on tabs or two-or-more spaces."""
    return re.split(r"\t+|\s{2,}", text.strip())


def parse_cli_table(
    lines: Sequence[str], max_columns: int | None = 6
) -> tuple[list[str], list[list[str]]]:
    """Parse CLI table-like output lines into headers and rows."""
    if not lines:
        return ([], [])

    headers = [header.strip() for header in split_cli_columns(lines[0])]
    if max_columns is not None:
        headers = headers[:max_columns]
    if not headers:
        return ([], [])

    rows: list[list[str]] = []
    header_count = len(headers)
    for data_line in lines[1:]:
        cols = [column.strip() for column in split_cli_columns(data_line)]
        if len(cols) < header_count:
            cols += [""] * (header_count - len(cols))
        elif len(cols) > header_count:
            cols = cols[: header_count - 1] + [" ".join(cols[header_count - 1 :])]
        rows.append(cols[:header_count])

    return (headers, rows)


def rows_to_dicts(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[dict[str, str]]:
    """Convert parsed table rows into JSON-friendly dict rows."""
    normalized_keys = [
        header.lower().replace("-", "_").replace(" ", "_") for header in headers
    ]
    return [dict(zip(normalized_keys, row)) for row in rows]

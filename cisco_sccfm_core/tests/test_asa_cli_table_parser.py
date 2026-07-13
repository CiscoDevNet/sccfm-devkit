# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from cisco_sccfm_core.parsers.asa_cli_table_parser import (
    normalize_cli_output,
    parse_cli_table,
    rows_to_dicts,
    split_cli_columns,
)


def test_normalize_cli_output_trims_blank_lines_and_keeps_content() -> None:
    raw = "  hello  \n\n  world  \n"
    assert normalize_cli_output(raw) == ["  hello", "  world"]


def test_normalize_cli_output_converts_escaped_tabs() -> None:
    assert normalize_cli_output("a\\tb") == ["a\tb"]


def test_split_cli_columns_splits_tabs_and_wide_spaces() -> None:
    assert split_cli_columns("A\tB  C") == ["A", "B", "C"]


def test_parse_cli_table_default_max_columns_is_six() -> None:
    lines = [
        "C1  C2  C3  C4  C5  C6  C7",
        "v1  v2  v3  v4  v5  v6  v7",
    ]
    headers, rows = parse_cli_table(lines)
    assert headers == ["C1", "C2", "C3", "C4", "C5", "C6"]
    assert rows == [["v1", "v2", "v3", "v4", "v5", "v6 v7"]]


def test_parse_cli_table_supports_unlimited_columns() -> None:
    lines = [
        "C1  C2  C3  C4  C5  C6  C7",
        "v1  v2  v3  v4  v5  v6  v7",
    ]
    headers, rows = parse_cli_table(lines, max_columns=None)
    assert headers == ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]
    assert rows == [["v1", "v2", "v3", "v4", "v5", "v6", "v7"]]


def test_rows_to_dicts_normalizes_headers() -> None:
    headers = ["Lock-time", "Failed Attempts", "User"]
    rows = [["10", "3", "admin"]]
    assert rows_to_dicts(headers, rows) == [
        {"lock_time": "10", "failed_attempts": "3", "user": "admin"}
    ]

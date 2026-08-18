# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import click

from cisco_sccfm_cli.commands.shared_options import (
    config_path_option,
    format_option,
    limit_option,
    offset_option,
)
from cisco_sccfm_cli.commands.shared_options import timeout_option as timeout_option
from cisco_sccfm_cli.commands.shared_options import wait_option as wait_option

__all__ = [
    "config_path_option",
    "format_option",
    "inventory_list_params",
    "limit_option",
    "offset_option",
    "query_option",
    "timeout_option",
    "wait_option",
]


def query_option(help_text: str | None = None) -> click.Option:
    """Reusable --query option for filtering.

    Args:
        help_text: Custom help text. Defaults to Lucene query description.
    """
    default_help = "The query to execute. Use the Lucene Query Syntax to construct your query."
    return click.Option(
        ["-q", "--query"],
        default=None,
        show_default=False,
        help=help_text or default_help,
    )


def inventory_list_params() -> list[click.Parameter]:
    """Complete set of options for inventory list commands."""
    return [
        limit_option(),
        offset_option(),
        query_option(),
        format_option(),
        config_path_option(),
    ]

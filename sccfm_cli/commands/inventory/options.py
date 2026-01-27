from __future__ import annotations

from pathlib import Path
from typing import List

import click


def limit_option() -> click.Option:
    """Reusable --limit option for pagination."""
    return click.Option(
        ["-l", "--limit"],
        default=50,
        show_default=True,
        type=click.IntRange(min=1, max=200),
        help="Maximum records to return",
    )


def offset_option() -> click.Option:
    """Reusable --offset option for pagination."""
    return click.Option(
        ["-o", "--offset"],
        default=0,
        show_default=True,
        type=click.IntRange(min=0),
        help="Pagination offset",
    )


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


def format_option() -> click.Option:
    """Reusable --format option for output formatting."""
    return click.Option(
        ["--format"],
        type=click.Choice(["table", "json"], case_sensitive=False),
        default="table",
        show_default=True,
        help="Output format",
    )


def config_path_option() -> click.Option:
    """Reusable --config-path option."""
    return click.Option(
        ["--config-path"],
        type=click.Path(path_type=Path, resolve_path=True),
        default=None,
        envvar="SCCFM_CONFIG",
        show_default=False,
        help="Path to the configuration file (defaults to ~/.sccfm-cli/config.json).",
    )


def inventory_list_params() -> List[click.Parameter]:
    """Complete set of options for inventory list commands."""
    return [
        limit_option(),
        offset_option(),
        query_option(),
        format_option(),
        config_path_option(),
    ]

from __future__ import annotations

from pathlib import Path
from typing import List

import click


def inventory_list_params() -> List[click.Parameter]:
    return [
        click.Option(
            ["--limit"],
            default=50,
            show_default=True,
            type=click.IntRange(min=1, max=200),
            help="Maximum records to return",
        ),
        click.Option(
            ["--offset"],
            default=0,
            show_default=True,
            type=click.IntRange(min=0),
            help="Pagination offset",
        ),
        click.Option(
            ["--query"],
            default=None,
            show_default=False,
            help=("The query to execute. Use the Lucene Query Syntax to construct your " "query."),
        ),
        click.Option(
            ["--format"],
            type=click.Choice(["table", "json"], case_sensitive=False),
            default="table",
            show_default=True,
            help="Output format",
        ),
        click.Option(
            ["--config-path"],
            type=click.Path(path_type=Path, resolve_path=True),
            default=None,
            envvar="SCCFM_CONFIG",
            show_default=False,
            help="Path to the configuration file (defaults to ~/.sccfm-cli/config.json).",
        ),
    ]

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import click

from cisco_sccfm_core.constants import DEFAULT_TRANSACTION_TIMEOUT_SEC


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
        type=click.Path(path_type=Path, resolve_path=False),
        default=None,
        envvar="SCCFM_CONFIG",
        show_default=False,
        help="Path to the configuration file (defaults to ~/.sccfm-cli/config.json).",
    )


def wait_option() -> click.Option:
    """Reusable --wait flag to poll a transaction until it finishes."""
    return click.Option(
        ["--wait/--no-wait"],
        default=False,
        show_default=True,
        help="Wait for the transaction to finish before returning.",
    )


def timeout_option(default: int = DEFAULT_TRANSACTION_TIMEOUT_SEC) -> click.Option:
    """Reusable --timeout option (seconds) for transaction polling."""
    return click.Option(
        ["--timeout"],
        type=click.IntRange(min=1),
        default=default,
        show_default=True,
        help="Maximum seconds to wait for the transaction to complete (used with --wait).",
    )


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

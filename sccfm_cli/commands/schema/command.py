# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence, cast

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.schema import build_cli_schema
from sccfm_cli.utils import json_text, print_json


class SchemaCommand(BaseCommand):
    """Command group for machine-readable CLI schema export."""

    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._export_command = SchemaExportCommand(console)

    @property
    def name(self) -> str:
        return "schema"

    @property
    def help_text(self) -> str:
        return "Export machine-readable command metadata."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        group.add_command(self._export_command.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail("Specify a subcommand: export")


class SchemaExportCommand(BaseCommand):
    """Export the live Click command tree as JSON."""

    @property
    def name(self) -> str:
        return "export"

    @property
    def help_text(self) -> str:
        return "Export the sccfm-cli command schema."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["--format"],
                type=click.Choice(["json"], case_sensitive=False),
                default="json",
                show_default=True,
                help="Schema output format.",
            ),
            click.Option(
                ["--output", "-o"],
                type=click.Path(dir_okay=False, path_type=Path),
                help="Write schema JSON to a file instead of stdout.",
            ),
        ]

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        output_format = cast(str, kwargs["format"])
        if output_format != "json":
            raise click.ClickException("Only JSON schema output is supported.")

        root = ctx.find_root()
        command = root.command
        if command is None:
            raise click.ClickException("Unable to locate the root Click command.")

        schema = build_cli_schema(command, prog_name=root.info_name or "sccfm-cli")
        output_path = cast(Path | None, kwargs.get("output"))
        if output_path is None:
            print_json(schema)
            return

        try:
            output_path.write_text(f"{json_text(schema)}\n", encoding="utf-8")
        except OSError as exc:
            raise click.ClickException(f"Unable to write schema output: {exc}") from exc

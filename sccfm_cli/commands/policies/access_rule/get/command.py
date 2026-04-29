from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.shared_options import config_path_option, format_option
from sccfm_cli.utils import print_json, with_spinner
from sccfm_core.services.policy import AccessRuleResponse, AccessRuleService


def _access_rule_get_params() -> list[click.Parameter]:
    return [
        click.Option(
            ["--uid"],
            required=True,
            type=str,
            help="UID of the access rule.",
        ),
        format_option(),
        config_path_option(),
    ]


class GetAccessRuleCommand(BaseCommand):
    """Get a single access rule by UID."""

    @property
    def name(self) -> str:
        return "get"

    @property
    def help_text(self) -> str:
        return "Get an ASA access rule by UID."

    def build_params(self) -> Sequence[click.Parameter]:
        return _access_rule_get_params()

    @with_spinner("Fetching access rule...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        config = self.get_profile(ctx=ctx, **kwargs)
        uid = cast(str, kwargs["uid"])
        output_format = cast(str, kwargs.get("format"))

        service = AccessRuleService(config)
        response = service.fetch_access_rule(uid=uid)
        self._render_response(response, output_format)

    def _render_response(self, response: AccessRuleResponse, output_format: str) -> None:
        if output_format == "json":
            print_json(response.to_dict())
            return

        table = Table(title="Access Rule", width=120)
        table.add_column("UID")
        table.add_column("Action")
        table.add_column("Source")
        table.add_column("Destination")
        table.add_column("Protocol")
        table.add_column("Dest Port")
        table.add_column("Index")
        src = (response.source_network or {}).get("name", "any")
        dst = (response.destination_network or {}).get("name", "any")
        proto = (response.protocol or {}).get("name", "ip")
        dport = (response.destination_port or {}).get("name", "any")
        table.add_row(
            response.uid,
            response.rule_action or "-",
            src,
            dst,
            proto,
            dport,
            str(response.index),
        )
        self.console.print(table)

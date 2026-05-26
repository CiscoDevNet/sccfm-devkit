# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.shared_options import config_path_option, format_option
from sccfm_cli.utils import print_json, with_spinner
from sccfm_core.services.policy import AccessRuleResponse, AccessRuleService

_UPDATE_FIELDS = [
    "--index",
    "--rule-action",
    "--remark",
    "--source-network",
    "--destination-network",
    "--protocol",
    "--source-port",
    "--destination-port",
    "--log-level",
    "--log-interval",
    "--active/--inactive",
]


def _access_rule_update_params() -> list[click.Parameter]:
    return [
        click.Option(
            ["--uid"],
            required=True,
            type=str,
            help="UID of the access rule to update.",
        ),
        click.Option(
            ["--index"],
            default=None,
            type=int,
            help="New position of the rule in the ordered list.",
        ),
        click.Option(
            ["--rule-action"],
            type=click.Choice(["PERMIT", "DENY"], case_sensitive=False),
            default=None,
            help="Rule action.",
        ),
        click.Option(
            ["--remark"],
            default=None,
            type=str,
            help="Human-readable description of the rule.",
        ),
        click.Option(
            ["--source-network"],
            default=None,
            type=str,
            help="Source network object name.",
        ),
        click.Option(
            ["--destination-network"],
            default=None,
            type=str,
            help="Destination network object name.",
        ),
        click.Option(
            ["--protocol"],
            default=None,
            type=str,
            help="Protocol (e.g. tcp, udp, ip).",
        ),
        click.Option(
            ["--source-port"],
            default=None,
            type=str,
            help="Source port or port range.",
        ),
        click.Option(
            ["--destination-port"],
            default=None,
            type=str,
            help="Destination port or port range.",
        ),
        click.Option(
            ["--log-level"],
            default=None,
            type=str,
            help="Log level.",
        ),
        click.Option(
            ["--log-interval"],
            default=None,
            type=int,
            help="Log interval in seconds.",
        ),
        click.Option(
            ["--active/--inactive"],
            default=None,
            help="Whether the rule is active.",
        ),
        format_option(),
        config_path_option(),
    ]


class UpdateAccessRuleCommand(BaseCommand):
    """Update an access rule in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "update"

    @property
    def help_text(self) -> str:
        return "Update an ASA access rule."

    def build_params(self) -> Sequence[click.Parameter]:
        return _access_rule_update_params()

    @with_spinner("Updating access rule...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str, kwargs["uid"])
        output_format = cast(str, kwargs.get("format"))

        update_values: dict[str, Any] = {
            "index": kwargs.get("index"),
            "rule_action": kwargs.get("rule_action"),
            "remark": kwargs.get("remark"),
            "source_network": kwargs.get("source_network"),
            "destination_network": kwargs.get("destination_network"),
            "protocol": kwargs.get("protocol"),
            "source_port": kwargs.get("source_port"),
            "destination_port": kwargs.get("destination_port"),
            "log_level": kwargs.get("log_level"),
            "log_interval": kwargs.get("log_interval"),
            "active": kwargs.get("active"),
        }

        if not any(v is not None for v in update_values.values()):
            ctx.fail(f"At least one update field must be provided: {', '.join(_UPDATE_FIELDS)}")

        config = self.get_profile(ctx=ctx, **kwargs)
        service = AccessRuleService(config)
        response = service.modify_access_rule(uid=uid, **update_values)
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
        self.console.print("[green]\u2713[/green] Access rule updated")
        self.console.print(table)

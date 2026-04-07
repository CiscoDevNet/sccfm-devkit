from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.utils import check_object_exists
from sccfm_cli.commands.shared_options import config_path_option, format_option
from sccfm_cli.utils import with_spinner
from sccfm_core.services import NetworkObjectService
from sccfm_core.services.policy import AccessRuleResponse, AccessRuleService


def _access_rule_create_params() -> list[click.Parameter]:
    return [
        click.Option(
            ["--access-group-uid"],
            required=True,
            type=str,
            help="UID of the access group.",
        ),
        click.Option(
            ["--entity-uid"],
            required=True,
            type=str,
            help="UID of the device or manager.",
        ),
        click.Option(
            ["--index"],
            required=True,
            type=int,
            help="Position of the rule in the ordered list.",
        ),
        click.Option(
            ["--rule-action"],
            type=click.Choice(["PERMIT", "DENY"], case_sensitive=False),
            default="PERMIT",
            show_default=True,
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
        click.Option(
            ["--check"],
            is_flag=True,
            default=False,
            help="Run a preflight check without performing the operation.",
        ),
        format_option(),
        config_path_option(),
    ]


class CreateAccessRuleCommand(BaseCommand):
    """Create an access rule in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "create"

    @property
    def help_text(self) -> str:
        return "Create an ASA access rule."

    def build_params(self) -> Sequence[click.Parameter]:
        return _access_rule_create_params()

    @with_spinner("Creating access rule...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        config = self.get_profile(ctx=ctx, **kwargs)
        output_format = cast(str, kwargs.get("format"))
        check = cast(bool, kwargs.get("check", False))

        if check:
            network_service = NetworkObjectService(config)
            source = cast(str | None, kwargs.get("source_network"))
            destination = cast(str | None, kwargs.get("destination_network"))
            if source:
                check_object_exists(
                    console=self.console,
                    uid=None,
                    name=source,
                    get_by_uid_fn=None,
                    get_by_name_fn=network_service.get_network_object_by_name,
                    object_name="Source network object",
                    output_format=output_format,
                    operation="update",
                )
            if destination:
                check_object_exists(
                    console=self.console,
                    uid=None,
                    name=destination,
                    get_by_uid_fn=None,
                    get_by_name_fn=network_service.get_network_object_by_name,
                    object_name="Destination network object",
                    output_format=output_format,
                    operation="update",
                )
            return

        service = AccessRuleService(config)

        response = service.create_access_rule(
            access_group_uid=cast(str, kwargs["access_group_uid"]),
            entity_uid=cast(str, kwargs["entity_uid"]),
            index=cast(int, kwargs["index"]),
            rule_action=cast(str, kwargs.get("rule_action") or "PERMIT"),
            remark=cast(str | None, kwargs.get("remark")),
            source_network=cast(str | None, kwargs.get("source_network")),
            destination_network=cast(str | None, kwargs.get("destination_network")),
            protocol=cast(str | None, kwargs.get("protocol")),
            source_port=cast(str | None, kwargs.get("source_port")),
            destination_port=cast(str | None, kwargs.get("destination_port")),
            log_level=cast(str | None, kwargs.get("log_level")),
            log_interval=cast(int | None, kwargs.get("log_interval")),
            active=cast(bool | None, kwargs.get("active")),
        )

        self._render_response(response, output_format)

    def _render_response(self, response: AccessRuleResponse, output_format: str) -> None:
        if output_format == "json":
            self.console.print(json.dumps(response.to_dict(), indent=2, default=str))
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
        self.console.print("[green]✓[/green] Access rule created")
        self.console.print(table)

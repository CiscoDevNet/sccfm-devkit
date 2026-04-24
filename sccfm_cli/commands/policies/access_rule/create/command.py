from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.utils import check_object_exists
from sccfm_cli.commands.shared_options import config_path_option, format_option
from sccfm_cli.utils import print_json, with_spinner
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
            self._run_check(config=config, kwargs=kwargs, output_format=output_format)
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

    def _run_check(self, *, config: Any, kwargs: dict[str, Any], output_format: str) -> None:
        network_service = NetworkObjectService(config)
        source = cast(str | None, kwargs.get("source_network"))
        destination = cast(str | None, kwargs.get("destination_network"))

        references: list[dict[str, Any]] = []
        if source:
            ref = check_object_exists(
                console=self.console,
                uid=None,
                name=source,
                get_by_uid_fn=None,
                get_by_name_fn=network_service.get_network_object_by_name,
                object_name="Source network object",
                output_format=output_format,
                operation="update",
                emit=False,
            )
            references.append(ref)
        if destination:
            ref = check_object_exists(
                console=self.console,
                uid=None,
                name=destination,
                get_by_uid_fn=None,
                get_by_name_fn=network_service.get_network_object_by_name,
                object_name="Destination network object",
                output_format=output_format,
                operation="update",
                emit=False,
            )
            references.append(ref)

        all_exist = all(ref["exists"] for ref in references)
        can_proceed = all_exist
        if not references:
            reason = "no_network_references"
        elif can_proceed:
            reason = "network_references_resolved"
        else:
            reason = "missing_network_references"

        result: dict[str, Any] = {
            "operation": "create",
            "entity_type": "Access rule",
            "access_group_uid": cast(str, kwargs["access_group_uid"]),
            "entity_uid": cast(str, kwargs["entity_uid"]),
            "index": cast(int, kwargs["index"]),
            "can_proceed": can_proceed,
            "reason": reason,
            "network_references": references,
        }
        self._render_check_result(result, output_format)

    def _render_check_result(self, result: dict[str, Any], output_format: str) -> None:
        if output_format == "json":
            print_json(result)
            return

        if result["can_proceed"]:
            self.console.print("[green]✓[/green] Access rule preflight passed; create can proceed.")
        else:
            self.console.print(
                "[yellow]![/yellow] Access rule preflight found issues; " "create would fail."
            )

        for ref in result["network_references"]:
            label = ref["entity_type"]
            name = ref["identifier"]
            if ref["exists"]:
                self.console.print(
                    f"  [green]✓[/green] {label} '{name}' exists (UID: {ref['uid']})"
                )
            else:
                self.console.print(f"  [yellow]![/yellow] {label} '{name}' not found")

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
        self.console.print("[green]✓[/green] Access rule created")
        self.console.print(table)

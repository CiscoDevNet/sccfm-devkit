from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.options import config_path_option, format_option
from sccfm_cli.utils import print_json, with_spinner
from sccfm_core.services.inventory.cdfmc_access_policy_service import (
    CdfmcAccessPolicyService,
    FmcAccessPolicy,
)


class ListAccessPoliciesCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "list"

    @property
    def help_text(self) -> str:
        return "List FMC access policies for a given domain."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["--domain-uid"],
                required=True,
                help="The FMC domain UID (fmcDomainUid from `sccfm inventory manager list`).",
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Fetching FMC access policies...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        domain_uid = cast(str, kwargs.get("domain_uid"))
        output_format = cast(str, kwargs.get("format"))
        config = self.get_profile(ctx=ctx, **kwargs)

        service = CdfmcAccessPolicyService(config)
        policies = service.get_access_policies(domain_uid)
        self._render(policies, output_format)

    def _render(self, policies: list[FmcAccessPolicy], output_format: str) -> None:
        if output_format == "json":
            print_json([{"uid": p.uid, "name": p.name} for p in policies])
            return

        table = Table(title="FMC Access Policies", width=80)
        table.add_column("UID")
        table.add_column("Name")
        for policy in policies:
            table.add_row(policy.uid, policy.name)
        self.console.print(table)

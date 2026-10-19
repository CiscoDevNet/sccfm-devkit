# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.shared_options import config_path_option
from cisco_sccfm_cli.utils import with_spinner
from cisco_sccfm_core.services.policy import AccessRuleService


def _access_rule_delete_params() -> list[click.Parameter]:
    return [
        click.Option(
            ["--uid"],
            required=True,
            type=str,
            help="UID of the access rule to delete.",
        ),
        config_path_option(),
    ]


class DeleteAccessRuleCommand(BaseCommand):
    """Delete an access rule in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "delete"

    @property
    def help_text(self) -> str:
        return "Delete an ASA access rule."

    def build_params(self) -> Sequence[click.Parameter]:
        return _access_rule_delete_params()

    @with_spinner("Deleting access rule...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str, kwargs["uid"])

        config = self.get_profile(ctx=ctx, **kwargs)
        service = AccessRuleService(config)
        deleted_uid = service.delete_access_rule(uid=uid)
        self.console.print(f"[green]\u2713[/green] Access rule deleted (UID: {deleted_uid})")

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import object_delete_params
from sccfm_cli.commands.objects.utils import (
    check_object_exists,
    format_delete_success,
    validate_identifier,
)
from sccfm_cli.utils import with_spinner
from sccfm_core.errors import NotFoundError
from sccfm_core.services import NetworkGroupService


class DeleteNetworkGroupCommand(BaseCommand):
    """Delete a network group object in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "delete"

    @property
    def help_text(self) -> str:
        return "Delete a network group object."

    def build_params(self) -> Sequence[click.Parameter]:
        return object_delete_params()

    @with_spinner("Deleting network group...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str | None, kwargs.get("uid"))
        name = cast(str | None, kwargs.get("name"))
        check = cast(bool, kwargs.get("check", False))

        validate_identifier(ctx, uid=uid, name=name)

        config = self.get_profile(ctx=ctx, **kwargs)
        service = NetworkGroupService(config)

        if check:
            check_object_exists(
                console=self.console,
                uid=uid,
                name=name,
                get_by_uid_fn=service.get_network_group,
                get_by_name_fn=service.get_network_group_by_name,
                object_name="Network group",
                operation="delete",
            )
            return

        try:
            deleted_uid = service.delete_network_group(uid=uid, name=name)
            identifier = name if name else uid
            self.console.print(format_delete_success("Network group", identifier, deleted_uid))
        except NotFoundError as e:
            ctx.fail(str(e))

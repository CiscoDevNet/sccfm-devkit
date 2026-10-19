# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.objects.options import object_delete_params
from cisco_sccfm_cli.commands.objects.utils import (
    check_object_exists,
    format_delete_success,
    validate_identifier,
)
from cisco_sccfm_cli.utils import with_spinner
from cisco_sccfm_core.errors import NotFoundError
from cisco_sccfm_core.services import NetworkObjectService


class DeleteNetworkObjectCommand(BaseCommand):
    """Delete a network object in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "delete"

    @property
    def help_text(self) -> str:
        return "Delete a network object."

    def build_params(self) -> Sequence[click.Parameter]:
        return object_delete_params()

    @with_spinner("Deleting network object...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str | None, kwargs.get("uid"))
        name = cast(str | None, kwargs.get("name"))
        check = cast(bool, kwargs.get("check", False))

        validate_identifier(ctx, uid=uid, name=name)

        config = self.get_profile(ctx=ctx, **kwargs)
        service = NetworkObjectService(config)

        if check:
            check_object_exists(
                console=self.console,
                uid=uid,
                name=name,
                get_by_uid_fn=service.get_network_object,
                get_by_name_fn=service.get_network_object_by_name,
                object_name="Network object",
                operation="delete",
            )
            return

        try:
            deleted_uid = service.delete_network_object(uid=uid, name=name)
            identifier = name if name else uid
            self.console.print(format_delete_success("Network object", identifier, deleted_uid))
        except NotFoundError as e:
            ctx.fail(str(e))

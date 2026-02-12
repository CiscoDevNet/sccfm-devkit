from __future__ import annotations

from typing import Any, Sequence, cast

import click

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import object_delete_params
from sccfm_cli.utils import with_spinner
from sccfm_core.errors import NotFoundError
from sccfm_core.services import NetworkObjectService


class NetworkDeleteCommand(BaseCommand):
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

        # Validate that exactly one of uid or name is provided
        if not uid and not name:
            ctx.fail("Either --uid or --name must be provided.")
        if uid and name:
            ctx.fail("Only one of --uid or --name should be provided, not both.")

        config = self.get_profile(ctx=ctx, **kwargs)
        service = NetworkObjectService(config)

        try:
            deleted_uid = service.delete_network_object(uid=uid, name=name)
            identifier = name if name else uid
            self.console.print(
                f"[green]\u2713[/green] Network object '{identifier}' "
                f"deleted successfully (UID: {deleted_uid})"
            )
        except NotFoundError as e:
            ctx.fail(str(e))

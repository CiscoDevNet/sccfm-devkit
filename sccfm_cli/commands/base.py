from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

import click
from rich.console import Console


class BaseCommand(ABC):
    """Base class implementing the command pattern for CLI commands."""

    def __init__(self, console: Console) -> None:
        self._console = console

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the Click command name."""

    @property
    def help_text(self) -> str:
        return ""

    def register(self, group: click.Group) -> None:
        group.add_command(self.build())

    def build(self) -> click.Command:
        return click.Command(
            name=self.name,
            help=self.help_text,
            callback=self._dispatch,
            params=list(self.build_params()),
        )

    def build_params(self) -> Sequence[click.Parameter]:
        return []

    def _dispatch(self, **kwargs: Any) -> None:
        ctx = click.get_current_context()
        self.handle(ctx=ctx, **kwargs)

    @abstractmethod
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        """Execute the command logic."""

    @property
    def console(self) -> Console:
        return self._console

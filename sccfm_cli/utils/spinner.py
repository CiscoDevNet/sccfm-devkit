from functools import wraps
from typing import Any, Callable, TypeVar

import click
from rich.live import Live
from rich.spinner import Spinner

F = TypeVar("F", bound=Callable[..., Any])


def with_spinner(text: str = "Processing...", console_attr: str = "console") -> Callable[[F], F]:
    """
    Decorator that displays a spinner while a function executes.
    The spinner is transient and will be cleared when execution completes.
    Respects the --silent global flag.

    Args:
        text: The text to display next to the spinner
        console_attr: The name of the console attribute on self (default: "console")

    Usage:
        @with_spinner("Fetching devices...")
        def handle(self, ctx: click.Context, **kwargs: Any) -> None:
            # Your code here
            # Uses self.console automatically
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check if silent mode is enabled
            ctx = click.get_current_context()
            silent = ctx.obj.get("silent", False) if ctx.obj else False

            # If silent mode, just run the function without spinner
            if silent:
                return func(*args, **kwargs)

            # Otherwise, show the spinner
            console = getattr(args[0], console_attr)
            spinner = Spinner("dots", text=text)

            with Live(spinner, console=console, refresh_per_second=10, transient=True):
                return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator

"""Shared utilities for object commands."""

from __future__ import annotations

from typing import Any

import click


def validate_identifier(
    ctx: click.Context,
    *,
    uid: str | None,
    name: str | None,
) -> None:
    """Validate that exactly one of uid or name is provided.

    Args:
        ctx: Click context for error handling.
        uid: The unique identifier.
        name: The name.

    Raises:
        click.exceptions.Exit: If validation fails.
    """
    if not uid and not name:
        ctx.fail("Either --uid or --name must be provided.")
    if uid and name:
        ctx.fail("Only one of --uid or --name should be provided, not both.")


def validate_has_updates(
    ctx: click.Context,
    *,
    fields: dict[str, Any],
    field_names: list[str],
) -> None:
    """Validate that at least one update field is provided.

    Args:
        ctx: Click context for error handling.
        fields: Dictionary of field name to value.
        field_names: Human-readable field names for error message.

    Raises:
        click.exceptions.Exit: If no update fields are provided.
    """
    if not any(fields.values()):
        names_str = ", ".join(field_names)
        ctx.fail(f"At least one update field must be provided: {names_str}.")


def format_delete_success(
    entity_type: str,
    identifier: str | None,
    deleted_uid: str,
) -> str:
    """Format a success message for delete operations.

    Args:
        entity_type: Type of entity deleted (e.g., "Network object").
        identifier: The identifier used (name or uid).
        deleted_uid: The UID of the deleted entity.

    Returns:
        Formatted success message with Rich markup.
    """
    return (
        f"[green]✓[/green] {entity_type} '{identifier}' "
        f"deleted successfully (UID: {deleted_uid})"
    )

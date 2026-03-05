"""Shared utilities for object commands."""

from __future__ import annotations

import json
from typing import Any, Callable, Literal, Protocol

import click
from rich.console import Console


class _HasUid(Protocol):
    @property
    def uid(self) -> str: ...

    @property
    def name(self) -> str: ...


CheckOperation = Literal["create", "update", "delete"]


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


def check_object_exists(
    *,
    console: Console,
    uid: str | None,
    name: str | None,
    get_by_uid_fn: Callable[[str], _HasUid | None] | None,
    get_by_name_fn: Callable[[str], _HasUid | None],
    object_name: str,
    output_format: str = "table",
    operation: CheckOperation = "update",
) -> None:
    """Check whether an object exists and print the result.

    Always exits with success (exit code 0).  When the entity is not
    found, an informational message is printed rather than a failure.

    Args:
        console: Rich console for output.
        uid: UID to look up (mutually exclusive with *name*).
        name: Name to look up (mutually exclusive with *uid*).
        get_by_uid_fn: Optional callable to look up by UID.
        get_by_name_fn: Callable to look up by name.
        object_name: Human-readable object label (e.g. "Network object").
        output_format: ``"table"`` for Rich output, ``"json"`` for JSON.
        operation: Intended mutation operation being preflight-checked.
    """
    identifier = uid or name
    entity: _HasUid | None = None

    if uid and get_by_uid_fn:
        entity = get_by_uid_fn(uid)
    elif name:
        entity = get_by_name_fn(name)

    exists = entity is not None
    found_uid = entity.uid if entity else None
    found_name = entity.name if entity else None

    if operation == "create":
        can_proceed = not exists
        reason = "not_found" if can_proceed else "already_exists"
        if exists:
            summary = f"{object_name} '{identifier}' already exists; create would fail."
        else:
            summary = f"{object_name} '{identifier}' not found; create can proceed."
    elif operation == "update":
        can_proceed = exists
        reason = "exists" if can_proceed else "not_found"
        if exists:
            summary = f"{object_name} '{identifier}' exists; update can proceed."
        else:
            summary = f"{object_name} '{identifier}' not found; update would fail."
    else:  # delete
        can_proceed = exists
        reason = "exists" if can_proceed else "not_found"
        if exists:
            summary = f"{object_name} '{identifier}' exists; delete can proceed."
        else:
            summary = f"{object_name} '{identifier}' not found; delete would fail."

    if output_format == "json":
        console.print(
            json.dumps(
                {
                    "entity_type": object_name,
                    "identifier": identifier,
                    "operation": operation,
                    "exists": exists,
                    "can_proceed": can_proceed,
                    "reason": reason,
                    "uid": found_uid,
                    "name": found_name,
                },
                indent=2,
            )
        )
        return

    if can_proceed:
        console.print(f"[green]✓[/green] {summary}")
    else:
        console.print(f"[yellow]![/yellow] {summary}")

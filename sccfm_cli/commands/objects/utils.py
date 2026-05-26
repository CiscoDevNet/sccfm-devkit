# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Shared utilities for object commands."""

from __future__ import annotations

import uuid as uuid_mod
from typing import Any, Callable, Literal, Protocol

import click
from rich.console import Console

from sccfm_cli.utils import print_json


class _HasUid(Protocol):
    @property
    def uid(self) -> str: ...

    @property
    def name(self) -> str: ...


class _NetworkObjectLookup(Protocol):
    def get_network_object(self, uid: str) -> _HasUid | None: ...

    def get_network_object_by_name(self, name: str) -> _HasUid | None: ...


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
    emit: bool = True,
) -> dict[str, Any]:
    """Check whether an object exists and optionally print the result.

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
        emit: Whether to print the result to the console.

    Returns:
        A dict describing the existence check result.
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
    else:
        can_proceed = exists
        reason = "exists" if can_proceed else "not_found"

    state = "not found" if operation == "create" else "exists"
    blocked_state = "already exists" if operation == "create" else "not found"
    if can_proceed:
        summary = f"{object_name} '{identifier}' {state}; {operation} can proceed."
    else:
        summary = f"{object_name} '{identifier}' {blocked_state}; {operation} would fail."

    result = {
        "entity_type": object_name,
        "identifier": identifier,
        "operation": operation,
        "exists": exists,
        "can_proceed": can_proceed,
        "reason": reason,
        "uid": found_uid,
        "name": found_name,
    }

    if not emit:
        return result

    if output_format == "json":
        print_json(result)
        return result

    if can_proceed:
        console.print(f"[green]✓[/green] {summary}")
    else:
        console.print(f"[yellow]![/yellow] {summary}")
    return result


def check_referenced_objects_exist(
    *,
    console: Console,
    referenced_objects: list[str],
    obj_service: _NetworkObjectLookup,
    output_format: str = "table",
    emit: bool = True,
) -> list[dict[str, Any]]:
    """Check whether referenced network objects exist and optionally print results.

    Each entry is resolved by UID (if it looks like a UUID) or by name.
    Always exits with success (exit code 0).

    Args:
        console: Rich console for output.
        referenced_objects: List of network object names or UIDs.
        obj_service: NetworkObjectService instance.
        output_format: ``"table"`` for Rich output, ``"json"`` for JSON.
        emit: Whether to print the results to the console.

    Returns:
        A list of dicts describing each referenced-object lookup result.
    """
    results: list[dict[str, Any]] = []
    for ref in referenced_objects:
        try:
            uid = str(uuid_mod.UUID(ref))
            entity = obj_service.get_network_object(uid)
        except ValueError:
            entity = obj_service.get_network_object_by_name(ref)

        exists = entity is not None
        found_uid = entity.uid if entity else None
        results.append({"identifier": ref, "exists": exists, "uid": found_uid})

    if not emit:
        return results

    if output_format == "json":
        print_json({"referenced_objects": results})
        return results

    for item in results:
        ref = item["identifier"]
        if item["exists"]:
            console.print(f"[green]✓[/green] Referenced object '{ref}' exists (UID: {item['uid']})")
        else:
            console.print(f"[yellow]![/yellow] Referenced object '{ref}' not found.")
    return results

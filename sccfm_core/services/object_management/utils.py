"""Shared utilities for object management services."""

from __future__ import annotations

from typing import Callable, Protocol, TypeVar

from sccfm_core.errors import NotFoundError


class HasUid(Protocol):
    """Protocol for objects with a uid attribute."""

    @property
    def uid(self) -> str: ...


T = TypeVar("T", bound=HasUid)


def resolve_uid(
    *,
    uid: str | None,
    name: str | None,
    get_by_name_fn: Callable[[str], T | None],
    get_by_uid_fn: Callable[[str], T | None] | None = None,
    entity_name: str,
) -> str:
    """Resolve an identifier (uid or name) to a UID.

    Validates that exactly one of uid or name is provided. If name is given,
    uses the lookup function to resolve it to a UID.

    Args:
        uid: The unique identifier of the object.
        name: The name of the object (resolved to UID via lookup).
        get_by_name_fn: Function to look up object by name, returns object or None.
        get_by_uid_fn: Optional function to verify UID exists, returns object or None.
        entity_name: Human-readable entity name for error messages (e.g., "network object").

    Returns:
        The resolved UID string.

    Raises:
        ValueError: If neither or both identifiers are provided.
        NotFoundError: If the object is not found.
    """
    if not uid and not name:
        raise ValueError("Either 'uid' or 'name' must be provided.")
    if uid and name:
        raise ValueError("Only one of 'uid' or 'name' should be provided, not both.")

    if name:
        obj = get_by_name_fn(name)
        if not obj:
            raise NotFoundError(f"{entity_name} with name '{name}' not found.")
        return obj.uid

    assert uid is not None
    if get_by_uid_fn:
        obj = get_by_uid_fn(uid)
        if not obj:
            raise NotFoundError(f"{entity_name} with UID '{uid}' not found.")
    return uid


def build_filtered_query(user_query: str | None, type_filter: str) -> str:
    """Append a type filter to the user's query.

    Args:
        user_query: Optional user-provided Lucene query string.
        type_filter: The object type filter (e.g., "objectType:NETWORK_OBJECT").

    Returns:
        Combined query string with the type filter.
    """
    if user_query:
        return f"{user_query} AND {type_filter}"
    return type_filter

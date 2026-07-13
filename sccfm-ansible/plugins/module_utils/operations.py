# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Shared operation utilities for Ansible modules."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Protocol, TypeVar

from scc_firewall_manager_sdk import ApiException

from cisco_sccfm_core.errors import NotFoundError, SccApiError

if TYPE_CHECKING:
    from ansible.module_utils.basic import AnsibleModule

T = TypeVar("T")


class HasUid(Protocol):
    """Protocol for objects with a uid attribute."""

    @property
    def uid(self) -> str: ...


class DeleteFunction(Protocol):
    """Protocol for delete functions that accept uid/name kwargs."""

    def __call__(self, *, uid: str | None, name: str | None) -> str: ...


class ResolveFunction(Protocol):
    """Protocol for functions that check existence (returns object or None)."""

    def __call__(self, uid: str) -> HasUid | None: ...


def fetch_object_by_identifier(
    *,
    uid: str | None,
    name: str | None,
    list_fn: Callable[[str, int], Any],
    get_by_name_fn: Callable[[str], T | None],
    entity_name: str,
) -> T:
    """Fetch an object by UID or name.

    Args:
        uid: The unique identifier of the object.
        name: The name of the object.
        list_fn: Function to list objects with query filter (takes query, limit).
        get_by_name_fn: Function to get object by name.
        entity_name: Human-readable entity name for error messages.

    Returns:
        The fetched object.

    Raises:
        NotFoundError: If the object cannot be found.
        ValueError: If neither uid nor name is provided.
    """
    if uid:
        result = list_fn(f'uid:"{uid}"', 1)
        if not result.items:
            raise NotFoundError(f"{entity_name} with UID '{uid}' not found.")
        return result.items[0]

    if name:
        obj = get_by_name_fn(name)
        if not obj:
            raise NotFoundError(f"{entity_name} with name '{name}' not found.")
        return obj

    raise ValueError("Either 'uid' or 'name' must be provided.")


def run_delete_with_idempotency(
    module: "AnsibleModule",
    *,
    delete_fn: DeleteFunction,
    uid: str | None,
    name: str | None,
    entity_name: str,
    get_by_uid_fn: Callable[[str], HasUid | None] | None = None,
    get_by_name_fn: Callable[[str], HasUid | None] | None = None,
) -> None:
    """Run a delete operation with idempotency and check_mode handling.

    In check_mode the function performs an existence check without
    deleting, using *get_by_uid_fn* / *get_by_name_fn* when provided.

    If the object doesn't exist, returns changed=False.
    On success, returns changed=True with the deleted UID.
    On error, calls module.fail_json().

    Args:
        module: The AnsibleModule instance.
        delete_fn: Function to delete object (takes uid and name kwargs).
        uid: The object UID.
        name: The object name.
        entity_name: Human-readable entity name for messages.
        get_by_uid_fn: Optional lookup function for check_mode by UID.
        get_by_name_fn: Optional lookup function for check_mode by name.
    """
    identifier = uid or name
    identifier_type = "UID" if uid else "name"

    if module.check_mode:
        _handle_delete_check_mode(
            module,
            uid=uid,
            name=name,
            entity_name=entity_name,
            identifier=identifier,
            get_by_uid_fn=get_by_uid_fn,
            get_by_name_fn=get_by_name_fn,
        )
        return

    try:
        deleted_uid = delete_fn(uid=uid, name=name)
        module.exit_json(
            changed=True,
            msg=f"Successfully deleted {entity_name} '{identifier}' ({identifier_type})",
            deleted_uid=deleted_uid,
        )
    except NotFoundError:
        module.exit_json(
            changed=False,
            msg=f"{entity_name} with {identifier_type} '{identifier}' not found; already absent.",
            deleted_uid=None,
        )
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict())
    except ValueError as e:
        module.fail_json(msg=f"Invalid parameters: {str(e)}")
    except Exception as e:
        module.fail_json(msg=f"Failed to delete {entity_name.lower()}: {str(e)}")


def _handle_delete_check_mode(
    module: "AnsibleModule",
    *,
    uid: str | None,
    name: str | None,
    entity_name: str,
    identifier: str | None,
    get_by_uid_fn: Callable[[str], HasUid | None] | None,
    get_by_name_fn: Callable[[str], HasUid | None] | None,
) -> None:
    """Report what a delete would do without performing it."""
    entity: HasUid | None = None
    try:
        if uid and get_by_uid_fn:
            entity = get_by_uid_fn(uid)
        elif name and get_by_name_fn:
            entity = get_by_name_fn(name)
    except NotFoundError:
        entity = None
    except ApiException as e:
        module.fail_json(**SccApiError.from_exception(e).to_dict(), deleted_uid=None)
        return
    except Exception as e:
        module.fail_json(
            msg=f"Failed to check {entity_name.lower()} existence: {str(e)}",
            deleted_uid=None,
        )
        return

    if entity:
        module.exit_json(
            changed=True,
            msg=f"Would delete {entity_name} '{identifier}'.",
            deleted_uid=entity.uid,
        )
    else:
        identifier_type = "UID" if uid else "name"
        module.exit_json(
            changed=False,
            msg=f"{entity_name} with {identifier_type} '{identifier}' not found; already absent.",
            deleted_uid=None,
        )


def fields_need_update(
    current: dict[str, Any],
    desired: dict[str, Any],
) -> bool:
    """Check if any desired fields differ from current values.

    Args:
        current: Dictionary of current field values.
        desired: Dictionary of desired field values
            (None values are skipped).

    Returns:
        True if at least one field needs to be updated.
    """
    for key, desired_value in desired.items():
        if desired_value is None:
            continue

        current_value = current.get(key)

        # Handle list comparison with sorting
        if isinstance(desired_value, list) and isinstance(current_value, list):
            if sorted(desired_value) != sorted(current_value):
                return True
        elif desired_value != current_value:
            return True

    return False

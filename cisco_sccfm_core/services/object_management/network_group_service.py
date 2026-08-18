# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Service for managing network groups via the SCC Firewall Manager API."""

from __future__ import annotations

import uuid
import warnings
from dataclasses import dataclass, field
from typing import Any, Literal

from scc_firewall_manager_sdk.models.create_request import CreateRequest
from scc_firewall_manager_sdk.models.group_content import GroupContent
from scc_firewall_manager_sdk.models.network_object_content import NetworkObjectContent
from scc_firewall_manager_sdk.models.object_content import ObjectContent
from scc_firewall_manager_sdk.models.shared_object_value import SharedObjectValue
from scc_firewall_manager_sdk.models.single_content import SingleContent
from scc_firewall_manager_sdk.models.update_request import UpdateRequest
from scc_firewall_manager_sdk.models.url_object_content import UrlObjectContent

from cisco_sccfm_core.errors import NotFoundError
from cisco_sccfm_core.services.object_management.network_object_service import NetworkObjectService
from cisco_sccfm_core.services.object_management.object_api_helper import ObjectApiHelper
from cisco_sccfm_core.services.object_management.utils import build_filtered_query, resolve_uid
from cisco_sccfm_core.types import ConfigLike


@dataclass
class NetworkGroupResponse:
    """Simplified response for a network group.

    The SDK's ObjectResponse has deserialization issues with oneOf schemas,
    so we parse the raw response into a simpler dataclass.
    """

    uid: str
    name: str
    description: str | None
    elements: list[str]
    labels: list[str]
    tags: dict[str, list[str]]
    object_type: str
    literals: list[str] = field(default_factory=lambda: [])
    referenced_object_uids: list[str] = field(default_factory=lambda: [])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NetworkGroupResponse:
        value: dict[str, Any] = data.get("value") or {}
        default_content: dict[str, Any] = value.get("defaultContent") or {}
        raw_literals: list[dict[str, Any]] = default_content.get("literals") or []
        raw_refs: list[str] = default_content.get("referencedObjectUids") or []

        literals = [
            str(item.get("literal") or item.get("url") or "")
            for item in raw_literals
            if item.get("literal") or item.get("url")
        ]

        return cls(
            uid=str(data.get("uid") or ""),
            name=str(data.get("name") or ""),
            description=data.get("description"),
            elements=list(data.get("elements") or []),
            labels=list(data.get("labels") or []),
            tags=dict(data.get("tags") or {}),
            object_type=str(value.get("objectType") or ""),
            literals=literals,
            referenced_object_uids=list(raw_refs),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "name": self.name,
            "description": self.description,
            "elements": self.elements,
            "labels": self.labels,
            "tags": self.tags,
            "object_type": self.object_type,
            "literals": self.literals,
            "referenced_object_uids": self.referenced_object_uids,
        }


@dataclass
class NetworkGroupMemberMutationResult:
    """Result of a network-group referenced-member mutation."""

    network_group: NetworkGroupResponse
    changed: bool


@dataclass
class NetworkGroupListResponse:
    """Paginated response for listing network groups.

    Mirrors the SDK's ListObjectResponse but uses our own
    NetworkGroupResponse items to avoid oneOf deserialization issues.
    """

    count: int
    items: list[NetworkGroupResponse]
    limit: int
    offset: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NetworkGroupListResponse:
        raw_items: list[dict[str, Any]] = data.get("items") or []
        return cls(
            count=int(data.get("count") or 0),
            items=[NetworkGroupResponse.from_dict(item) for item in raw_items],
            limit=int(data.get("limit") or 0),
            offset=int(data.get("offset") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "items": [item.to_dict() for item in self.items],
            "limit": self.limit,
            "offset": self.offset,
        }


class NetworkGroupService:
    """Service for managing network groups via the SCC Firewall Manager API."""

    OBJECT_TYPE = "NETWORK_GROUP"
    GROUP_TYPE_FILTER = f"objectType:{OBJECT_TYPE}"

    def __init__(self, config: ConfigLike) -> None:
        self._helper = ObjectApiHelper(config)
        self._object_api = self._helper.api
        self._network_object_service = NetworkObjectService(config)

    def get_network_group(self, uid: str) -> NetworkGroupResponse | None:
        """Fetch a network group by UID.

        Returns ``None`` when the UID does not exist **or** when it
        resolves to a different object type (e.g. a plain network object).

        Args:
            uid: The unique identifier of the network group.

        Returns:
            The NetworkGroupResponse if found and type-correct, None otherwise.

        Raises:
            ApiException: If the API call fails with a non-404 error.
        """
        response = self._object_api.get_object_without_preload_content(uid=uid)
        if response.status == 404:
            return None
        data = self._helper.read_raw_response(response)
        parsed = NetworkGroupResponse.from_dict(data)
        if parsed.object_type != self.OBJECT_TYPE:
            return None
        return parsed

    def _get_raw_group_content(self, uid: str) -> dict[str, Any]:
        """Fetch the raw defaultContent dict for a network group.

        Used during updates to preserve the existing literals or referenced
        objects that are not being changed.

        Args:
            uid: The unique identifier of the network group.

        Returns:
            The raw defaultContent dict from the API response.

        Raises:
            NotFoundError: If the group is not found.
        """
        data = self._get_raw_group_data(uid)
        value: dict[str, Any] = data.get("value") or {}
        return value.get("defaultContent") or {}

    def _get_raw_group_data(self, uid: str) -> dict[str, Any]:
        """Fetch the raw object payload for a network group."""
        response = self._object_api.get_object_without_preload_content(uid=uid)
        if response.status == 404:
            raise NotFoundError(f"Network group with UID '{uid}' not found.")
        return self._helper.read_raw_response(response)

    def get_network_group_by_name(self, name: str) -> NetworkGroupResponse | None:
        """Search for a network group object by name.

        Uses an objectType filter so that plain network objects with the
        same name are not matched.

        Args:
            name: The name of the network group to find.

        Returns:
            The NetworkGroupResponse if found, None otherwise.

        Raises:
            ApiException: If the API call fails.
        """
        query = f'name:"{name}" AND {self.GROUP_TYPE_FILTER}'
        response = self._object_api.get_objects_without_preload_content(q=query, limit="1")
        data = self._helper.read_raw_response(response)

        items = data.get("items", [])
        if not items:
            return None

        return NetworkGroupResponse.from_dict(items[0])

    def delete_network_group(self, uid: str | None = None, name: str | None = None) -> str:
        """Delete a network group object by UID or name.

        Args:
            uid: The unique identifier of the network group to delete.
            name: The name of the network group to delete.

        Returns:
            The UID of the deleted object.

        Raises:
            ValueError: If neither uid nor name is provided, or both are provided.
            NotFoundError: If the group with the given name is not found.
            ApiException: If the deletion fails.
        """
        resolved_uid = self._resolve_uid(uid=uid, name=name)
        response = self._object_api.delete_object_without_preload_content(uid=resolved_uid)
        self._helper.check_raw_response(response)
        return resolved_uid

    def list_network_groups(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        query: str | None = None,
    ) -> NetworkGroupListResponse:
        """List network groups with optional filtering.

        Args:
            limit: Maximum number of results to return.
            offset: Pagination offset.
            query: Optional Lucene query string (searchable fields: name, content).

        Returns:
            A paginated NetworkGroupListResponse.
        """
        response = self._object_api.get_objects_without_preload_content(
            limit=str(limit),
            offset=str(offset),
            q=build_filtered_query(query, self.GROUP_TYPE_FILTER),
        )
        data = self._helper.read_raw_response(response)
        return NetworkGroupListResponse.from_dict(data)

    def _resolve_uid(self, *, uid: str | None, name: str | None) -> str:
        """Resolve a network group identifier to a UID."""
        return resolve_uid(
            uid=uid,
            name=name,
            get_by_name_fn=self.get_network_group_by_name,
            get_by_uid_fn=self.get_network_group,
            entity_name="Network group",
        )

    def create_network_group(
        self,
        *,
        name: str,
        network_literals: list[str] | None = None,
        url_literals: list[str] | None = None,
        referenced_objects: list[str] | None = None,
        description: str | None = None,
        labels: list[str] | None = None,
        tags: dict[str, list[str]] | None = None,
    ) -> NetworkGroupResponse:
        """Create a network group.

        Args:
            name: The name of the network group.
            network_literals: Inline network literals (IP addresses, CIDRs, ranges).
            url_literals: Inline URL literals.
            referenced_objects: UIDs or names of existing network objects to include.
            description: Optional description for the group.
            labels: Optional list of labels to attach to the group.
            tags: Optional dict of tag keys to lists of tag values.

        Returns:
            The created NetworkGroupResponse from the API.

        Raises:
            ValueError: If no content is provided.
            ValueError: If both network_literals and url_literals are provided.
            ValueError: If any literal value is empty or blank.
            ValueError: If any referenced object value is empty or blank.
            NotFoundError: If a referenced object name cannot be resolved to a UID.
        """
        has_literals = bool(network_literals or url_literals)
        if not has_literals and not referenced_objects:
            raise ValueError(
                "At least one literal or referenced object is required "
                "to create a network group."
            )
        if network_literals and url_literals:
            raise ValueError(
                "Only one literal type is allowed per group. "
                "Provide network_literals or url_literals, not both."
            )
        self._validate_literals(network_literals or url_literals or [])
        self._validate_referenced_objects(referenced_objects or [])
        resolved_uids = self._resolve_referenced_object_uids(referenced_objects or [])
        single_contents = self._build_literal_contents(
            network_literals=network_literals or [],
            url_literals=url_literals or [],
        )
        shared_value = self._build_shared_value(
            single_contents=single_contents,
            referenced_object_uids=resolved_uids,
        )
        create_request = CreateRequest(
            name=name,
            value=shared_value,
            description=description,
            labels=labels,
            tags=tags,
        )
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Pydantic serializer warnings",
                category=UserWarning,
            )
            response = self._object_api.create_object_without_preload_content(
                create_request=create_request,
            )
        data = self._helper.read_raw_response(response)
        return NetworkGroupResponse.from_dict(data)

    def update_network_group(
        self,
        *,
        uid: str | None = None,
        name: str | None = None,
        new_name: str | None = None,
        referenced_objects: list[str] | None = None,
        description: str | None = None,
        labels: list[str] | None = None,
        tags: dict[str, list[str]] | None = None,
    ) -> NetworkGroupResponse:
        """Update a network group by UID or name.

        Args:
            uid: The unique identifier of the network group to update.
            name: The name of the network group to update (resolved to UID).
            new_name: Optional new name for the group.
            referenced_objects: UIDs or names of existing network objects to
                reference. Replaces all existing referenced objects but
                preserves any existing literals.
            description: Optional new description.
            labels: Optional new labels.
            tags: Optional new tags.

        Returns:
            The updated NetworkGroupResponse from the API.

        Raises:
            ValueError: If neither uid nor name is provided, or both are provided.
            ValueError: If any referenced object value is empty or blank.
            NotFoundError: If the group or a referenced object is not found.
        """
        resolved_uid = self._resolve_uid(uid=uid, name=name)

        shared_value: SharedObjectValue | None = None
        if referenced_objects is not None:
            self._validate_referenced_objects(referenced_objects)
            resolved_uids = self._resolve_referenced_object_uids(referenced_objects)
            current_content = self._get_raw_group_content(resolved_uid)
            existing_literals = self._rebuild_literal_contents(current_content)
            shared_value = self._build_shared_value(
                single_contents=existing_literals,
                referenced_object_uids=resolved_uids,
            )

        update_request = UpdateRequest(
            name=new_name,
            value=shared_value,
            description=description,
            labels=labels,
            tags=tags,
        )
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Pydantic serializer warnings",
                category=UserWarning,
            )
            response = self._object_api.modify_object_without_preload_content(
                uid=resolved_uid,
                update_request=update_request,
            )
        data = self._helper.read_raw_response(response)
        return NetworkGroupResponse.from_dict(data)

    def add_network_group_members(
        self,
        *,
        uid: str | None = None,
        name: str | None = None,
        referenced_objects: list[str],
        apply_changes: bool = True,
    ) -> NetworkGroupMemberMutationResult:
        """Add referenced network-object members to a network group."""
        return self._mutate_network_group_members(
            uid=uid,
            name=name,
            referenced_objects=referenced_objects,
            operation="add",
            apply_changes=apply_changes,
        )

    def remove_network_group_members(
        self,
        *,
        uid: str | None = None,
        name: str | None = None,
        referenced_objects: list[str],
        apply_changes: bool = True,
    ) -> NetworkGroupMemberMutationResult:
        """Remove referenced network-object members from a network group."""
        return self._mutate_network_group_members(
            uid=uid,
            name=name,
            referenced_objects=referenced_objects,
            operation="remove",
            apply_changes=apply_changes,
        )

    def _mutate_network_group_members(
        self,
        *,
        uid: str | None,
        name: str | None,
        referenced_objects: list[str],
        operation: Literal["add", "remove"],
        apply_changes: bool,
    ) -> NetworkGroupMemberMutationResult:
        """Best-effort read/modify/write for referenced network-object members."""
        resolved_uid = self._resolve_uid(uid=uid, name=name)
        self._validate_referenced_objects(referenced_objects)

        current_data = self._get_raw_group_data(resolved_uid)
        current_group = NetworkGroupResponse.from_dict(current_data)
        resolved_refs = self._resolve_referenced_object_uids(referenced_objects)
        final_refs = self._merge_referenced_object_uids(
            current_group.referenced_object_uids,
            resolved_refs,
            operation=operation,
        )
        changed = final_refs != current_group.referenced_object_uids
        if not changed or not apply_changes:
            return NetworkGroupMemberMutationResult(
                network_group=current_group,
                changed=changed,
            )

        current_content = self._extract_default_content(current_data)
        existing_literals = self._rebuild_literal_contents(current_content)
        shared_value = self._build_shared_value(
            single_contents=existing_literals,
            referenced_object_uids=final_refs,
        )
        update_request = UpdateRequest(value=shared_value)
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Pydantic serializer warnings",
                category=UserWarning,
            )
            response = self._object_api.modify_object_without_preload_content(
                uid=resolved_uid,
                update_request=update_request,
            )
        data = self._helper.read_raw_response(response)
        return NetworkGroupMemberMutationResult(
            network_group=NetworkGroupResponse.from_dict(data),
            changed=True,
        )

    def _build_shared_value(
        self,
        *,
        single_contents: list[SingleContent],
        referenced_object_uids: list[str],
    ) -> SharedObjectValue:
        """Build a SharedObjectValue for a network group.

        Args:
            single_contents: Pre-built SingleContent literals.
            referenced_object_uids: UIDs of existing objects to reference.

        Returns:
            A SharedObjectValue wrapping the GroupContent.
        """
        group_content = GroupContent(
            literals=single_contents if single_contents else None,
            referenced_object_uids=referenced_object_uids if referenced_object_uids else None,
        )
        object_content = ObjectContent(actual_instance=group_content)
        return SharedObjectValue(
            defaultContent=object_content,
            objectType=self.OBJECT_TYPE,
        )

    @staticmethod
    def _build_literal_contents(
        *,
        network_literals: list[str],
        url_literals: list[str],
    ) -> list[SingleContent]:
        """Build SingleContent objects from typed literal values.

        Args:
            network_literals: Network literal strings (IPs, CIDRs, ranges).
            url_literals: URL literal strings.

        Returns:
            A list of SingleContent wrapping the appropriate content type.
        """
        contents: list[SingleContent] = []
        for lit in network_literals:
            contents.append(SingleContent(actual_instance=NetworkObjectContent(literal=lit)))
        for url in url_literals:
            contents.append(SingleContent(actual_instance=UrlObjectContent(url=url)))
        return contents

    @staticmethod
    def _extract_default_content(raw_data: dict[str, Any]) -> dict[str, Any]:
        """Extract the raw defaultContent dict from a group payload."""
        value: dict[str, Any] = raw_data.get("value") or {}
        return value.get("defaultContent") or {}

    @staticmethod
    def _rebuild_literal_contents(
        raw_content: dict[str, Any],
    ) -> list[SingleContent]:
        """Reconstruct SingleContent objects from raw API content.

        Inspects each literal dict to determine whether it is a network
        literal (has ``literal`` key) or a URL literal (has ``url`` key)
        and wraps it in the appropriate SDK model.

        Args:
            raw_content: The raw ``defaultContent`` dict from the API.

        Returns:
            A list of SingleContent preserving the original literal types.
        """
        raw_literals: list[dict[str, Any]] = raw_content.get("literals") or []
        contents: list[SingleContent] = []
        for item in raw_literals:
            if item.get("url"):
                contents.append(
                    SingleContent(actual_instance=UrlObjectContent(url=item["url"])),
                )
            elif item.get("literal"):
                contents.append(
                    SingleContent(
                        actual_instance=NetworkObjectContent(literal=item["literal"]),
                    ),
                )
        return contents

    def _resolve_referenced_object_uids(self, referenced_objects: list[str]) -> list[str]:
        """Resolve referenced object identifiers to UIDs.

        Each value is checked: if it is a valid UUID, its existence and
        type are verified via the network object service; otherwise it
        is treated as a name and looked up.

        Args:
            referenced_objects: Values that may be UIDs or object names.

        Returns:
            A list of resolved UID strings.

        Raises:
            NotFoundError: If a referenced object cannot be found or is
                not a network object.
        """
        resolved: list[str] = []
        for ref in referenced_objects:
            if self._is_uuid(ref):
                obj = self._network_object_service.get_network_object(uid=ref)
                if not obj:
                    raise NotFoundError(f"Network object with UID '{ref}' not found.")
                resolved.append(obj.uid)
            else:
                obj = self._network_object_service.get_network_object_by_name(name=ref)
                if not obj:
                    raise NotFoundError(f"Network object with name '{ref}' not found.")
                resolved.append(obj.uid)
        return resolved

    @staticmethod
    def _merge_referenced_object_uids(
        current_uids: list[str],
        requested_uids: list[str],
        *,
        operation: Literal["add", "remove"],
    ) -> list[str]:
        """Merge referenced-object UIDs while preserving stable order."""
        current = NetworkGroupService._dedupe_preserve_order(current_uids)
        requested = NetworkGroupService._dedupe_preserve_order(requested_uids)
        if operation == "add":
            return NetworkGroupService._dedupe_preserve_order([*current, *requested])

        requested_set = set(requested)
        return [uid for uid in current if uid not in requested_set]

    @staticmethod
    def _dedupe_preserve_order(values: list[str]) -> list[str]:
        """Remove duplicates while preserving first-seen order."""
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    @staticmethod
    def _is_uuid(value: str) -> bool:
        """Check whether a string is a valid UUID.

        Args:
            value: The string to check.

        Returns:
            True if the string is a valid UUID, False otherwise.
        """
        try:
            uuid.UUID(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def _validate_literals(literals: list[str]) -> None:
        """Ensure every literal value is non-empty.

        Args:
            literals: Literal values to validate.

        Raises:
            ValueError: If any literal is empty or blank.
        """
        blank = [i for i, v in enumerate(literals, start=1) if not v or not v.strip()]
        if blank:
            positions = ", ".join(str(p) for p in blank)
            raise ValueError(
                f"Literal values must not be empty (blank at position(s): {positions})."
            )

    @staticmethod
    def _validate_referenced_objects(referenced_objects: list[str]) -> None:
        """Ensure every referenced object identifier is non-empty.

        Args:
            referenced_objects: Referenced object UIDs or names to validate.

        Raises:
            ValueError: If any referenced object value is empty or blank.
        """
        blank = [i for i, v in enumerate(referenced_objects, start=1) if not v or not v.strip()]
        if blank:
            positions = ", ".join(str(p) for p in blank)
            raise ValueError(
                f"Referenced object UIDs must not be empty (blank at position(s): {positions})."
            )

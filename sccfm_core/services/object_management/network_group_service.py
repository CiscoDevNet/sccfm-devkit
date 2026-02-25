"""Service for managing network groups via the SCC Firewall Manager API."""

from __future__ import annotations

import uuid
import warnings
from dataclasses import dataclass, field
from typing import Any

from scc_firewall_manager_sdk.models.create_request import CreateRequest
from scc_firewall_manager_sdk.models.group_content import GroupContent
from scc_firewall_manager_sdk.models.network_object_content import NetworkObjectContent
from scc_firewall_manager_sdk.models.object_content import ObjectContent
from scc_firewall_manager_sdk.models.shared_object_value import SharedObjectValue
from scc_firewall_manager_sdk.models.single_content import SingleContent
from scc_firewall_manager_sdk.models.url_object_content import UrlObjectContent

from sccfm_core.errors import NotFoundError
from sccfm_core.services.object_management.network_object_service import NetworkObjectService
from sccfm_core.services.object_management.object_api_helper import ObjectApiHelper
from sccfm_core.types import ConfigLike


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


class NetworkGroupService:
    """Service for managing network groups via the SCC Firewall Manager API."""

    OBJECT_TYPE = "NETWORK_GROUP"
    GROUP_TYPE_FILTER = "objectType:NETWORK_GROUP"

    def __init__(self, config: ConfigLike) -> None:
        self._helper = ObjectApiHelper(config)
        self._object_api = self._helper.api
        self._network_object_service = NetworkObjectService(config)

    def _get_network_group(self, uid: str) -> NetworkGroupResponse | None:
        """Fetch a network group by UID.

        Args:
            uid: The unique identifier of the network group.

        Returns:
            The NetworkGroupResponse if found, None if a 404 is returned.

        Raises:
            ApiException: If the API call fails with a non-404 error.
        """
        response = self._object_api.get_object_without_preload_content(uid=uid)
        if response.status == 404:
            return None
        data = self._helper.read_raw_response(response)
        return NetworkGroupResponse.from_dict(data)

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

    def _resolve_uid(self, *, uid: str | None, name: str | None) -> str:
        """Resolve a network group identifier to a UID.

        Validates that exactly one of uid or name is provided. If name is
        given, queries the API with an objectType filter to find the UID.

        Args:
            uid: The unique identifier of the network group.
            name: The name of the network group (resolved to UID via API lookup).

        Returns:
            The resolved UID string.

        Raises:
            ValueError: If neither or both identifiers are provided.
            NotFoundError: If the network group is not found.
        """
        if not uid and not name:
            raise ValueError("Either 'uid' or 'name' must be provided.")
        if uid and name:
            raise ValueError("Only one of 'uid' or 'name' should be provided, not both.")

        if name:
            obj = self.get_network_group_by_name(name)
            if not obj:
                raise NotFoundError(f"Network group with name '{name}' not found.")
            return obj.uid

        assert uid is not None
        obj = self._get_network_group(uid)
        if not obj:
            raise NotFoundError(f"Network group with UID '{uid}' not found.")
        return uid

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

    def _resolve_referenced_object_uids(self, referenced_objects: list[str]) -> list[str]:
        """Resolve referenced object identifiers to UIDs.

        Each value is checked: if it is a valid UUID, it is used as-is;
        otherwise it is treated as a name and looked up via the network
        object API.

        Args:
            referenced_objects: Values that may be UIDs or object names.

        Returns:
            A list of resolved UID strings.

        Raises:
            NotFoundError: If a referenced object name cannot be found.
        """
        resolved: list[str] = []
        for ref in referenced_objects:
            if self._is_uuid(ref):
                resolved.append(ref)
            else:
                obj = self._network_object_service.get_network_object_by_name(ref)
                if not obj:
                    raise NotFoundError(f"Network object with name '{ref}' not found.")
                resolved.append(obj.uid)
        return resolved

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

"""Service for managing network groups via the SCC Firewall Manager API."""

from __future__ import annotations

import uuid
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
    literals: list[str] = field(default_factory=list)
    referenced_object_uids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NetworkGroupResponse:
        value: dict[str, Any] = data.get("value") or {}
        default_content: dict[str, Any] = value.get("defaultContent") or {}
        raw_literals: list[dict[str, Any]] = default_content.get("literals") or []
        raw_refs: list[str] = default_content.get("referencedObjectUids") or []

        literals = [
            str(item.get("literal") or "") for item in raw_literals if item.get("literal")
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

    def __init__(self, config: ConfigLike) -> None:
        self._helper = ObjectApiHelper(config)
        self._object_api = self._helper.api
        self._network_object_service = NetworkObjectService(config)

    def create_network_group(
        self,
        *,
        name: str,
        network_literals: list[str] | None = None,
        url_literals: list[str] | None = None,
        members: list[str] | None = None,
        description: str | None = None,
        labels: list[str] | None = None,
        tags: dict[str, list[str]] | None = None,
    ) -> NetworkGroupResponse:
        """Create a network group.

        Args:
            name: The name of the network group.
            network_literals: Inline network literals (IP addresses, CIDRs, ranges).
            url_literals: Inline URL literals.
            members: UIDs or names of existing network objects to include.
            description: Optional description for the group.
            labels: Optional list of labels to attach to the group.
            tags: Optional dict of tag keys to lists of tag values.

        Returns:
            The created NetworkGroupResponse from the API.

        Raises:
            ValueError: If no content is provided.
            ValueError: If both network_literals and url_literals are provided.
            ValueError: If any literal value is empty or blank.
            ValueError: If any member value is empty or blank.
            NotFoundError: If a member name cannot be resolved to a UID.
        """
        has_literals = bool(network_literals or url_literals)
        if not has_literals and not members:
            raise ValueError(
                "At least one literal or member is required "
                "to create a network group."
            )
        if network_literals and url_literals:
            raise ValueError(
                "Only one literal type is allowed per group. "
                "Provide network_literals or url_literals, not both."
            )
        self._validate_literals(network_literals or url_literals or [])
        self._validate_members(members or [])
        resolved_members = self._resolve_member_uids(members or [])
        single_contents = self._build_literal_contents(
            network_literals=network_literals or [],
            url_literals=url_literals or [],
        )
        shared_value = self._build_shared_value(
            single_contents=single_contents,
            members=resolved_members,
        )
        create_request = CreateRequest(
            name=name,
            value=shared_value,
            description=description,
            labels=labels,
            tags=tags,
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
        members: list[str],
    ) -> SharedObjectValue:
        """Build a SharedObjectValue for a network group.

        Args:
            single_contents: Pre-built SingleContent literals.
            members: UIDs of existing objects to reference.

        Returns:
            A SharedObjectValue wrapping the GroupContent.
        """
        group_content = GroupContent(
            literals=single_contents if single_contents else None,
            referenced_object_uids=members if members else None,
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
            contents.append(
                SingleContent(actual_instance=NetworkObjectContent(literal=lit))
            )
        for url in url_literals:
            contents.append(
                SingleContent(actual_instance=UrlObjectContent(url=url))
            )
        return contents

    def _resolve_member_uids(self, members: list[str]) -> list[str]:
        """Resolve member identifiers to UIDs.

        Each member value is checked: if it is a valid UUIDv4, it is used
        as-is; otherwise it is treated as a name and looked up via the
        network object API.

        Args:
            members: Member values that may be UIDs or object names.

        Returns:
            A list of resolved UID strings.

        Raises:
            NotFoundError: If a member name cannot be found.
        """
        resolved: list[str] = []
        for member in members:
            if self._is_uuid(member):
                resolved.append(member)
            else:
                obj = self._network_object_service.get_network_object_by_name(member)
                if not obj:
                    raise NotFoundError(
                        f"Network object with name '{member}' not found."
                    )
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
    def _validate_members(members: list[str]) -> None:
        """Ensure every member identifier is non-empty.

        Args:
            members: Member UIDs or names to validate.

        Raises:
            ValueError: If any member value is empty or blank.
        """
        blank = [i for i, v in enumerate(members, start=1) if not v or not v.strip()]
        if blank:
            positions = ", ".join(str(p) for p in blank)
            raise ValueError(
                f"Member UIDs must not be empty (blank at position(s): {positions})."
            )

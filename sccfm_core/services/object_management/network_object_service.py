from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from scc_firewall_manager_sdk.api.object_management_api import ObjectManagementApi
from scc_firewall_manager_sdk.exceptions import ApiException
from scc_firewall_manager_sdk.models.create_request import CreateRequest
from scc_firewall_manager_sdk.models.network_object_content import NetworkObjectContent
from scc_firewall_manager_sdk.models.object_content import ObjectContent
from scc_firewall_manager_sdk.models.shared_object_value import SharedObjectValue

from sccfm_core.errors import NotFoundError
from sccfm_core.factories import ApiClientFactory
from sccfm_core.types import ConfigLike


@dataclass
class NetworkObjectResponse:
    """Simplified response for network object creation.

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
    literal: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NetworkObjectResponse":
        value: dict[str, Any] = data.get("value") or {}
        default_content: dict[str, Any] = value.get("defaultContent") or {}
        return cls(
            uid=str(data.get("uid") or ""),
            name=str(data.get("name") or ""),
            description=data.get("description"),
            elements=list(data.get("elements") or []),
            labels=list(data.get("labels") or []),
            tags=dict(data.get("tags") or {}),
            object_type=str(value.get("objectType") or ""),
            literal=str(default_content.get("literal") or ""),
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
            "literal": self.literal,
        }


@dataclass
class NetworkObjectListResponse:
    """Paginated response for listing network objects.

    Mirrors the SDK's ListObjectResponse but uses our own
    NetworkObjectResponse items to avoid oneOf deserialization issues.
    """

    count: int
    items: list[NetworkObjectResponse]
    limit: int
    offset: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NetworkObjectListResponse":
        raw_items: list[dict[str, Any]] = data.get("items") or []
        return cls(
            count=int(data.get("count") or 0),
            items=[NetworkObjectResponse.from_dict(item) for item in raw_items],
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


class NetworkObjectService:
    """Service for managing network objects via the SCC Firewall Manager API."""

    OBJECT_TYPE = "NETWORK_OBJECT"
    NETWORK_TYPE_FILTER = "objectType:*NETWORK*"

    def __init__(self, config: ConfigLike) -> None:
        api_client = ApiClientFactory().build(config)
        self._object_api = ObjectManagementApi(api_client)

    def create_network_object(
        self,
        *,
        name: str,
        value: str,
        description: str | None = None,
        labels: list[str] | None = None,
        tags: dict[str, list[str]] | None = None,
    ) -> NetworkObjectResponse:
        """Create a network object.

        Args:
            name: The name of the network object.
            value: The literal value (e.g., IP address, CIDR, range).
            description: Optional description for the object.
            labels: Optional list of labels to attach to the object.
            tags: Optional dict of tag keys to lists of tag values.

        Returns:
            The created NetworkObjectResponse from the API.
        """
        network_content = NetworkObjectContent(literal=value)
        object_content = ObjectContent(actual_instance=network_content)
        shared_value = SharedObjectValue(
            defaultContent=object_content,
            objectType=self.OBJECT_TYPE,
        )
        create_request = CreateRequest(
            name=name,
            value=shared_value,
            description=description,
            labels=labels,
            tags=tags,
        )
        response = self._object_api.create_object_without_preload_content(
            create_request=create_request
        )
        data = self._read_raw_response(response)
        return NetworkObjectResponse.from_dict(data)

    def get_network_object_by_name(self, name: str) -> NetworkObjectResponse | None:
        """Search for a network object by name.

        Args:
            name: The name of the network object to find.

        Returns:
            The NetworkObjectResponse if found, None otherwise.

        Raises:
            ApiException: If the API call fails.
        """
        # Use Lucene query syntax to search by name
        query = f'name:"{name}"'
        response = self._object_api.get_objects_without_preload_content(q=query, limit="1")
        data = self._read_raw_response(response)

        # Check if we found any results
        items = data.get("items", [])
        if not items:
            return None

        return NetworkObjectResponse.from_dict(items[0])

    def delete_network_object(self, uid: str | None = None, name: str | None = None) -> str:
        """Delete a network object by UID or name.

        Args:
            uid: The unique identifier of the network object to delete.
            name: The name of the network object to delete.

        Returns:
            The UID of the deleted object.

        Raises:
            ValueError: If neither uid nor name is provided, or both are provided.
            NotFoundError: If the object with the given name is not found.
            ApiException: If the deletion fails.
        """
        if not uid and not name:
            raise ValueError("Either 'uid' or 'name' must be provided.")
        if uid and name:
            raise ValueError("Only one of 'uid' or 'name' should be provided, not both.")

        # If name is provided, resolve it to UID first
        if name:
            obj = self.get_network_object_by_name(name)
            if not obj:
                raise NotFoundError(f"Network object with name '{name}' not found.")
            uid = obj.uid

        # At this point uid is guaranteed to be a non-None string
        assert uid is not None, "UID should not be None after validation"
        response = self._object_api.delete_object_without_preload_content(uid=uid)
        self._check_raw_response(response)
        return uid

    def list_network_objects(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        query: str | None = None,
    ) -> NetworkObjectListResponse:
        """List network objects with optional filtering.

        Args:
            limit: Maximum number of results to return.
            offset: Pagination offset.
            query: Optional Lucene query string (searchable fields: name, content).

        Returns:
            A paginated NetworkObjectListResponse.
        """
        response = self._object_api.get_objects_without_preload_content(
            limit=str(limit),
            offset=str(offset),
            q=self._build_query(query),
        )
        data = self._read_raw_response(response)
        return NetworkObjectListResponse.from_dict(data)

    @classmethod
    def _build_query(cls, query: str | None) -> str:
        """Append the network object type filter to the user's query.

        Ensures only NETWORK_OBJECT and NETWORK_GROUP types are returned.
        """
        if query:
            return f"{query} AND {cls.NETWORK_TYPE_FILTER}"
        return cls.NETWORK_TYPE_FILTER

    @staticmethod
    def _read_raw_response(response: Any) -> dict[str, Any]:
        """Read and validate a raw HTTP response, returning parsed JSON."""
        raw_data = response.read()
        body = raw_data.decode("utf-8")
        _raise_for_status(response.status, body)
        return dict(json.loads(body))

    @staticmethod
    def _check_raw_response(response: Any) -> None:
        """Read and validate a raw HTTP response that may have an empty body."""
        raw_data = response.read()
        body = raw_data.decode("utf-8")
        _raise_for_status(response.status, body)


def _raise_for_status(status: int, body: str) -> None:
    """Raise an ApiException if the HTTP status indicates an error."""
    if 200 <= status < 300:
        return
    raise ApiException(status=status, body=body)

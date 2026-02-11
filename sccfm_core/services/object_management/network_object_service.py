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


class NetworkObjectService:
    """Service for managing network objects via the SCC Firewall Manager API."""

    OBJECT_TYPE = "NETWORK_OBJECT"

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
        # Use the raw response method to avoid SDK deserialization bugs with oneOf
        response = self._object_api.create_object_without_preload_content(
            create_request=create_request
        )
        raw_data = response.read()
        body = raw_data.decode("utf-8")
        self._raise_for_status(response.status, body)
        data = json.loads(body)
        return NetworkObjectResponse.from_dict(data)

    @staticmethod
    def _raise_for_status(status: int, body: str) -> None:
        """Raise an ApiException if the HTTP status indicates an error."""
        if 200 <= status < 300:
            return
        raise ApiException(status=status, body=body)

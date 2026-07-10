# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Service for adding device-specific overrides to objects."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

from scc_firewall_manager_sdk.models.network_object_content import NetworkObjectContent
from scc_firewall_manager_sdk.models.object_content import ObjectContent
from scc_firewall_manager_sdk.models.override import Override
from scc_firewall_manager_sdk.models.shared_object_value import SharedObjectValue
from scc_firewall_manager_sdk.models.update_request import UpdateRequest
from scc_firewall_manager_sdk.models.url_object_content import UrlObjectContent

from cisco_sccfm_core.services.object_management.object_api_helper import ObjectApiHelper
from cisco_sccfm_core.types import ConfigLike

_SUPPORTED_TYPES = {"NETWORK_OBJECT", "URL_OBJECT"}


@dataclass
class ObjectTargetItem:
    """A single target (device) that an object is attached to."""

    id: str
    display_name: str
    type: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObjectTargetItem":
        return cls(
            id=str(data.get("id") or ""),
            display_name=str(data.get("displayName") or ""),
            type=str(data.get("type") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "display_name": self.display_name, "type": self.type}


@dataclass
class ObjectTargetsResponse:
    """Targets (devices) an object is attached to."""

    uid: str
    name: str
    targets: list[ObjectTargetItem]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObjectTargetsResponse":
        raw_targets: list[dict[str, Any]] = data.get("targets") or []
        return cls(
            uid=str(data.get("uid") or ""),
            name=str(data.get("name") or ""),
            targets=[ObjectTargetItem.from_dict(t) for t in raw_targets],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "name": self.name,
            "targets": [t.to_dict() for t in self.targets],
        }


@dataclass
class UpdateDefaultValueResponse:
    """Response for update-default-value operations."""

    uid: str
    name: str
    object_type: str
    default_value: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpdateDefaultValueResponse":
        value: dict[str, Any] = data.get("value") or {}
        default_content: dict[str, Any] = value.get("defaultContent") or {}
        literal = default_content.get("literal") or default_content.get("url") or ""
        return cls(
            uid=str(data.get("uid") or ""),
            name=str(data.get("name") or ""),
            object_type=str(value.get("objectType") or ""),
            default_value=str(literal),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "name": self.name,
            "object_type": self.object_type,
            "default_value": self.default_value,
        }


@dataclass
class ObjectOverrideResponse:
    """Simplified response for object override operations."""

    uid: str
    name: str
    object_type: str
    overrides_count: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObjectOverrideResponse":
        value: dict[str, Any] = data.get("value") or {}
        overrides: list[Any] = value.get("overrides") or []
        return cls(
            uid=str(data.get("uid") or ""),
            name=str(data.get("name") or ""),
            object_type=str(value.get("objectType") or ""),
            overrides_count=len(overrides),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "name": self.name,
            "object_type": self.object_type,
            "overrides_count": self.overrides_count,
        }


@dataclass
class ObjectOverrideItem:
    """A single override entry on an object."""

    target_id: str
    value: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObjectOverrideItem":
        content: dict[str, Any] = data.get("content") or {}
        value = str(content.get("literal") or content.get("url") or "")
        return cls(target_id=str(data.get("targetId") or ""), value=value)

    def to_dict(self) -> dict[str, Any]:
        return {"target_id": self.target_id, "value": self.value}


@dataclass
class ObjectDetailsResponse:
    """Full details of an object, including default value, overrides, and targets."""

    uid: str
    name: str
    description: str
    object_type: str
    default_value: str
    overrides: list[ObjectOverrideItem]
    targets: list[ObjectTargetItem]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObjectDetailsResponse":
        value: dict[str, Any] = data.get("value") or {}
        default_content: dict[str, Any] = value.get("defaultContent") or {}
        default_value = str(default_content.get("literal") or default_content.get("url") or "")
        raw_overrides: list[dict[str, Any]] = value.get("overrides") or []
        raw_targets: list[dict[str, Any]] = data.get("targets") or []
        return cls(
            uid=str(data.get("uid") or ""),
            name=str(data.get("name") or ""),
            description=str(data.get("description") or ""),
            object_type=str(value.get("objectType") or ""),
            default_value=default_value,
            overrides=[ObjectOverrideItem.from_dict(o) for o in raw_overrides],
            targets=[ObjectTargetItem.from_dict(t) for t in raw_targets],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "name": self.name,
            "description": self.description,
            "object_type": self.object_type,
            "default_value": self.default_value,
            "overrides": [o.to_dict() for o in self.overrides],
            "targets": [t.to_dict() for t in self.targets],
        }


class ObjectOverrideService:
    """Service for adding device-specific overrides to objects.

    Supports NETWORK_OBJECT and URL_OBJECT types. The object must be
    attached to at least one device (non-empty ``targets``) for overrides
    to be applicable.
    """

    def __init__(self, config: ConfigLike) -> None:
        self._helper = ObjectApiHelper(config)
        self._object_api = self._helper.api

    def get_targets(self, *, uid: str) -> ObjectTargetsResponse:
        """Fetch the list of devices an object is attached to.

        Args:
            uid: The unique identifier of the object.

        Returns:
            ObjectTargetsResponse with the list of attached targets.

        Raises:
            ApiException: If the API call fails.
        """
        response = self._object_api.get_object_without_preload_content(uid=uid)
        data = self._helper.read_raw_response(response)
        return ObjectTargetsResponse.from_dict(data)

    def get_object(self, *, uid: str) -> ObjectDetailsResponse:
        """Fetch the full details of an object.

        Args:
            uid: The unique identifier of the object.

        Returns:
            ObjectDetailsResponse with all object details.

        Raises:
            ApiException: If the API call fails.
        """
        response = self._object_api.get_object_without_preload_content(uid=uid)
        data = self._helper.read_raw_response(response)
        return ObjectDetailsResponse.from_dict(data)

    def add_override(
        self,
        *,
        uid: str,
        target_id: str,
        override_value: str,
    ) -> ObjectOverrideResponse:
        """Add a device-specific override to an object.

        Fetches the current object state, validates device attachment,
        preserves the existing ``defaultContent`` and any existing overrides,
        then PATCHes the object with the new override appended.

        Args:
            uid: The unique identifier of the object.
            target_id: The UID of the target device for the override.
            override_value: The literal value for the override content.

        Returns:
            ObjectOverrideResponse reflecting the updated object.

        Raises:
            ValueError: If the object is not attached to any device.
            ValueError: If the object type is not supported for overrides.
            ApiException: If the API call fails.
        """
        response = self._object_api.get_object_without_preload_content(uid=uid)
        data = self._helper.read_raw_response(response)

        targets: list[Any] = data.get("targets") or []
        if not targets:
            raise ValueError(
                "Object is not attached to any device; overrides require device attachment."
            )

        value: dict[str, Any] = data.get("value") or {}
        object_type = str(value.get("objectType") or "")
        if object_type not in _SUPPORTED_TYPES:
            raise ValueError(
                f"Overrides are not supported for object type '{object_type}'. "
                f"Supported types: {', '.join(sorted(_SUPPORTED_TYPES))}."
            )

        raw_default_content: dict[str, Any] = value.get("defaultContent") or {}
        raw_overrides: list[dict[str, Any]] = value.get("overrides") or []

        default_content = self._build_object_content(raw_default_content, object_type)
        existing_overrides = [
            self._build_override_from_raw(raw_override, object_type)
            for raw_override in raw_overrides
        ]
        new_override = Override(
            content=self._build_content_from_value(override_value, object_type),
            targetId=target_id,
        )

        shared_value = SharedObjectValue(
            defaultContent=default_content,
            objectType=object_type,
            overrides=existing_overrides + [new_override],
        )
        update_request = UpdateRequest(value=shared_value)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Pydantic serializer warnings")
            patch_response = self._object_api.modify_object_without_preload_content(
                uid=uid,
                update_request=update_request,
            )
        result_data = self._helper.read_raw_response(patch_response)
        return ObjectOverrideResponse.from_dict(result_data)

    def edit_override(
        self,
        *,
        uid: str,
        target_id: str,
        new_value: str,
    ) -> ObjectOverrideResponse:
        """Edit the value of an existing override for a specific target device.

        Fetches the current object state, locates the override matching
        ``target_id``, replaces its content with ``new_value``, and PATCHes
        the object with all other overrides and ``defaultContent`` preserved.

        Args:
            uid: The unique identifier of the object.
            target_id: The UID of the target device whose override to edit.
            new_value: The new literal value for the override content.

        Returns:
            ObjectOverrideResponse reflecting the updated object.

        Raises:
            ValueError: If no override exists for the given target ID.
            ValueError: If the object type is not supported.
            ApiException: If the API call fails.
        """
        response = self._object_api.get_object_without_preload_content(uid=uid)
        data = self._helper.read_raw_response(response)

        value: dict[str, Any] = data.get("value") or {}
        object_type = str(value.get("objectType") or "")
        if object_type not in _SUPPORTED_TYPES:
            raise ValueError(
                f"Editing overrides is not supported for object type '{object_type}'. "
                f"Supported types: {', '.join(sorted(_SUPPORTED_TYPES))}."
            )

        raw_overrides: list[dict[str, Any]] = value.get("overrides") or []
        if not any(o.get("targetId") == target_id for o in raw_overrides):
            raise ValueError(
                f"No override found for target ID '{target_id}'. "
                "Use 'add-override' to create a new one."
            )

        updated_overrides = [
            (
                Override(
                    content=self._build_content_from_value(new_value, object_type),
                    targetId=target_id,
                )
                if o.get("targetId") == target_id
                else self._build_override_from_raw(o, object_type)
            )
            for o in raw_overrides
        ]

        raw_default_content: dict[str, Any] = value.get("defaultContent") or {}
        default_content = self._build_object_content(raw_default_content, object_type)
        shared_value = SharedObjectValue(
            defaultContent=default_content,
            objectType=object_type,
            overrides=updated_overrides,
        )
        update_request = UpdateRequest(value=shared_value)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Pydantic serializer warnings")
            patch_response = self._object_api.modify_object_without_preload_content(
                uid=uid,
                update_request=update_request,
            )
        result_data = self._helper.read_raw_response(patch_response)
        return ObjectOverrideResponse.from_dict(result_data)

    def delete_override(
        self,
        *,
        uid: str,
        target_id: str,
    ) -> ObjectOverrideResponse:
        """Delete an existing override for a specific target device.

        Fetches the current object state, removes the override matching
        ``target_id``, and PATCHes the object with all remaining overrides
        and ``defaultContent`` preserved.

        Args:
            uid: The unique identifier of the object.
            target_id: The UID of the target device whose override to delete.

        Returns:
            ObjectOverrideResponse reflecting the updated object.

        Raises:
            ValueError: If no override exists for the given target ID.
            ValueError: If the object type is not supported.
            ApiException: If the API call fails.
        """
        response = self._object_api.get_object_without_preload_content(uid=uid)
        data = self._helper.read_raw_response(response)

        value: dict[str, Any] = data.get("value") or {}
        object_type = str(value.get("objectType") or "")
        if object_type not in _SUPPORTED_TYPES:
            raise ValueError(
                f"Deleting overrides is not supported for object type '{object_type}'. "
                f"Supported types: {', '.join(sorted(_SUPPORTED_TYPES))}."
            )

        raw_overrides: list[dict[str, Any]] = value.get("overrides") or []
        if not any(o.get("targetId") == target_id for o in raw_overrides):
            raise ValueError(f"No override found for target ID '{target_id}'.")

        remaining_overrides = [
            self._build_override_from_raw(o, object_type)
            for o in raw_overrides
            if o.get("targetId") != target_id
        ]

        raw_default_content: dict[str, Any] = value.get("defaultContent") or {}
        default_content = self._build_object_content(raw_default_content, object_type)
        shared_value = SharedObjectValue(
            defaultContent=default_content,
            objectType=object_type,
            overrides=remaining_overrides if remaining_overrides else None,
        )
        update_request = UpdateRequest(value=shared_value)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Pydantic serializer warnings")
            patch_response = self._object_api.modify_object_without_preload_content(
                uid=uid,
                update_request=update_request,
            )
        result_data = self._helper.read_raw_response(patch_response)
        return ObjectOverrideResponse.from_dict(result_data)

    def promote_override(
        self,
        *,
        uid: str,
        target_id: str,
    ) -> ObjectOverrideResponse:
        """Promote an existing override to become the new default value.

        Fetches the current object state, extracts the override content for
        ``target_id``, sets it as the new ``defaultContent``, removes that
        override from the list, and PATCHes the object with all other overrides
        preserved.

        Args:
            uid: The unique identifier of the object.
            target_id: The UID of the target device whose override to promote.

        Returns:
            ObjectOverrideResponse reflecting the updated object.

        Raises:
            ValueError: If no override exists for the given target ID.
            ValueError: If the object type is not supported.
            ApiException: If the API call fails.
        """
        response = self._object_api.get_object_without_preload_content(uid=uid)
        data = self._helper.read_raw_response(response)

        value: dict[str, Any] = data.get("value") or {}
        object_type = str(value.get("objectType") or "")
        if object_type not in _SUPPORTED_TYPES:
            raise ValueError(
                f"Promoting overrides is not supported for object type '{object_type}'. "
                f"Supported types: {', '.join(sorted(_SUPPORTED_TYPES))}."
            )

        raw_overrides: list[dict[str, Any]] = value.get("overrides") or []
        matching = next((o for o in raw_overrides if o.get("targetId") == target_id), None)
        if matching is None:
            raise ValueError(
                f"No override found for target ID '{target_id}'. "
                "Use 'add-override' to create a new one."
            )

        new_default_content = self._build_object_content(matching.get("content") or {}, object_type)
        remaining_overrides = [
            self._build_override_from_raw(o, object_type)
            for o in raw_overrides
            if o.get("targetId") != target_id
        ]

        shared_value = SharedObjectValue(
            defaultContent=new_default_content,
            objectType=object_type,
            overrides=remaining_overrides if remaining_overrides else None,
        )
        update_request = UpdateRequest(value=shared_value)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Pydantic serializer warnings")
            patch_response = self._object_api.modify_object_without_preload_content(
                uid=uid,
                update_request=update_request,
            )
        result_data = self._helper.read_raw_response(patch_response)
        return ObjectOverrideResponse.from_dict(result_data)

    def update_default_value(
        self,
        *,
        uid: str,
        new_value: str,
    ) -> UpdateDefaultValueResponse:
        """Update the default content value of an object, preserving all overrides.

        Fetches the current object state, replaces ``defaultContent`` with
        the new value, and PATCHes the object with the existing overrides intact.

        Args:
            uid: The unique identifier of the object.
            new_value: The new literal value for the default content.

        Returns:
            UpdateDefaultValueResponse reflecting the updated object.

        Raises:
            ValueError: If the object type is not supported.
            ApiException: If the API call fails.
        """
        response = self._object_api.get_object_without_preload_content(uid=uid)
        data = self._helper.read_raw_response(response)

        value: dict[str, Any] = data.get("value") or {}
        object_type = str(value.get("objectType") or "")
        if object_type not in _SUPPORTED_TYPES:
            raise ValueError(
                f"Updating default value is not supported for object type '{object_type}'. "
                f"Supported types: {', '.join(sorted(_SUPPORTED_TYPES))}."
            )

        raw_overrides: list[dict[str, Any]] = value.get("overrides") or []
        existing_overrides = [
            self._build_override_from_raw(raw_override, object_type)
            for raw_override in raw_overrides
        ]

        new_default_content = self._build_content_from_value(new_value, object_type)
        shared_value = SharedObjectValue(
            defaultContent=new_default_content,
            objectType=object_type,
            overrides=existing_overrides if existing_overrides else None,
        )
        update_request = UpdateRequest(value=shared_value)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Pydantic serializer warnings")
            patch_response = self._object_api.modify_object_without_preload_content(
                uid=uid,
                update_request=update_request,
            )
        result_data = self._helper.read_raw_response(patch_response)
        return UpdateDefaultValueResponse.from_dict(result_data)

    def _build_object_content(self, raw_content: dict[str, Any], object_type: str) -> ObjectContent:
        """Reconstruct an ObjectContent SDK model from a raw dict."""
        if object_type == "NETWORK_OBJECT":
            return ObjectContent(
                actual_instance=NetworkObjectContent(literal=str(raw_content["literal"]))
            )
        if object_type == "URL_OBJECT":
            return ObjectContent(actual_instance=UrlObjectContent(url=str(raw_content["url"])))
        raise ValueError(f"Unsupported object type: {object_type}")

    def _build_content_from_value(self, value: str, object_type: str) -> ObjectContent:
        """Build an ObjectContent from the CLI override value string."""
        if object_type == "NETWORK_OBJECT":
            return ObjectContent(actual_instance=NetworkObjectContent(literal=value))
        if object_type == "URL_OBJECT":
            return ObjectContent(actual_instance=UrlObjectContent(url=value))
        raise ValueError(f"Unsupported object type: {object_type}")

    def _build_override_from_raw(self, raw_override: dict[str, Any], object_type: str) -> Override:
        """Reconstruct an Override SDK object from a raw dict."""
        raw_content: dict[str, Any] = raw_override.get("content") or {}
        return Override(
            content=self._build_object_content(raw_content, object_type),
            targetId=raw_override.get("targetId"),
        )

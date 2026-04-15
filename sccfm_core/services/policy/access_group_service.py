from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sccfm_core.services.policy.policy_api_helper import PolicyApiHelper
from sccfm_core.types import ConfigLike


@dataclass
class AccessGroupResponse:
    """Simplified response for access group operations."""

    uid: str
    name: str
    entity_uid: str
    is_shared: bool | None
    shared_access_group_uid: str | None
    applied_to: list[str] | None
    resources: list[dict[str, Any]] | None
    created_date: str | None
    updated_date: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccessGroupResponse:
        return cls(
            uid=str(data.get("uid") or ""),
            name=str(data.get("name") or ""),
            entity_uid=str(data.get("entityUid") or ""),
            is_shared=data.get("isShared"),
            shared_access_group_uid=data.get("sharedAccessGroupUid"),
            applied_to=data.get("appliedTo"),
            resources=data.get("resources"),
            created_date=data.get("createdDate"),
            updated_date=data.get("updatedDate"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "name": self.name,
            "entity_uid": self.entity_uid,
            "is_shared": self.is_shared,
            "shared_access_group_uid": self.shared_access_group_uid,
            "applied_to": self.applied_to,
            "resources": self.resources,
            "created_date": self.created_date,
            "updated_date": self.updated_date,
        }


@dataclass
class AccessGroupListResponse:
    """Paginated response for listing access groups."""

    count: int
    items: list[AccessGroupResponse]
    limit: int
    offset: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccessGroupListResponse:
        raw_items: list[dict[str, Any]] = data.get("items") or []
        return cls(
            count=int(data.get("count") or 0),
            items=[AccessGroupResponse.from_dict(item) for item in raw_items],
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


class AccessGroupService:
    """Service for reading ASA access groups via the SCC Firewall Manager API."""

    def __init__(self, config: ConfigLike) -> None:
        self._helper = PolicyApiHelper(config)
        self._groups_api = self._helper.groups_api

    def fetch_access_group(self, *, uid: str) -> AccessGroupResponse:
        """Fetch a single access group by UID."""
        response = self._groups_api.fetch_access_group_without_preload_content(access_group_uid=uid)
        data = self._helper.read_raw_response(response)
        return AccessGroupResponse.from_dict(data)

    def list_access_groups(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        query: str | None = None,
    ) -> AccessGroupListResponse:
        """List access groups with optional pagination and search.

        Args:
            limit: Maximum number of results to return.
            offset: Pagination offset.
            query: Optional Lucene query string.
        """
        response = self._groups_api.list_access_groups_without_preload_content(
            limit=str(limit),
            offset=str(offset),
            q=query,
        )
        data = self._helper.read_raw_response(response)
        return AccessGroupListResponse.from_dict(data)

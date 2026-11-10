# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

import pytest

from cisco_sccfm_core.services.object_management.object_override_service import (
    ObjectDetailsResponse,
    ObjectOverrideService,
    ObjectTargetsResponse,
)

SAMPLE_DETAILS: dict[str, Any] = {
    "uid": "obj-1",
    "name": "web-server",
    "description": "Primary web server",
    "value": {
        "objectType": "NETWORK_OBJECT",
        "defaultContent": {"literal": "10.0.0.1"},
        "overrides": [{"targetId": "device-1", "content": {"literal": "10.0.0.2"}}],
    },
    "targets": [{"id": "device-1", "displayName": "ftd-1", "type": "FTD"}],
}


def _service() -> ObjectOverrideService:
    return ObjectOverrideService.__new__(ObjectOverrideService)


class TestObjectDetailsResponseFromDict:
    def test_parses_full_response(self) -> None:
        details = ObjectDetailsResponse.from_dict(SAMPLE_DETAILS)

        assert details.to_dict() == {
            "uid": "obj-1",
            "name": "web-server",
            "description": "Primary web server",
            "object_type": "NETWORK_OBJECT",
            "default_value": "10.0.0.1",
            "overrides": [{"target_id": "device-1", "value": "10.0.0.2"}],
            "targets": [{"id": "device-1", "display_name": "ftd-1", "type": "FTD"}],
        }

    def test_missing_fields_become_empty_strings(self) -> None:
        details = ObjectDetailsResponse.from_dict({"value": {"overrides": [{}]}, "targets": [{}]})

        assert (details.uid, details.name, details.description, details.object_type) == (
            "",
            "",
            "",
            "",
        )
        assert details.overrides[0].target_id == ""
        assert details.targets[0].display_name == ""


class TestObjectTargetsResponseFromDict:
    def test_missing_identity_becomes_empty_strings(self) -> None:
        targets = ObjectTargetsResponse.from_dict({"targets": []})

        assert targets.to_dict() == {"uid": "", "name": "", "targets": []}


class TestBuildOverrideFromRaw:
    @pytest.mark.parametrize(
        ("object_type", "content"),
        [("NETWORK_OBJECT", {"literal": "10.0.0.2"}), ("URL_OBJECT", {"url": "example.com"})],
    )
    def test_preserves_target_and_content(self, object_type: str, content: dict[str, str]) -> None:
        raw = {"targetId": "device-1", "content": content}

        override = _service()._build_override_from_raw(raw, object_type)

        assert override.to_dict() == {"targetId": "device-1", "content": content}

    def test_rejects_unsupported_object_type(self) -> None:
        with pytest.raises(ValueError, match="Unsupported object type"):
            _service()._build_override_from_raw({"content": {}}, "SERVICE_OBJECT")

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services.object_management import (
    ObjectDetailsResponse,
    ObjectOverrideItem,
    ObjectOverrideService,
    ObjectTargetItem,
)
from sccfm_core.services.object_management.object_api_helper import ObjectApiHelper

SAMPLE_RESPONSE = ObjectDetailsResponse(
    uid="fd526e22-12ff-4fa0-a88d-7375c5d1e144",
    name="000_fqdn_fafa_renamed",
    description="",
    object_type="NETWORK_OBJECT",
    default_value="hr88.cisco.com",
    overrides=[
        ObjectOverrideItem(target_id="0b2f5a0d-6ccb-45e6-a65c-7d9dd48d7b55", value="11.10.11.122"),
        ObjectOverrideItem(target_id="897b293f-132e-4678-9d78-0f0947629500", value="11.14.11.14"),
    ],
    targets=[
        ObjectTargetItem(
            id="897b293f-132e-4678-9d78-0f0947629500",
            display_name="alex-fdm-template",
            type="FDM_MANAGED_FTD",
        ),
        ObjectTargetItem(
            id="0b2f5a0d-6ccb-45e6-a65c-7d9dd48d7b55",
            display_name="alex-fercal-crush-ftd-template",
            type="FDM_MANAGED_FTD",
        ),
    ],
)


def _stub_init(self: ObjectOverrideService, config: Any) -> None:
    return None


class TestShowObjectCommand:
    """Tests for the get command happy path."""

    def test_should_get_object(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_get(self: ObjectOverrideService, **kwargs: Any) -> ObjectDetailsResponse:
            captured.update(kwargs)
            return SAMPLE_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "get_object", fake_get)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "show",
                "--uid",
                "fd526e22-12ff-4fa0-a88d-7375c5d1e144",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert captured["uid"] == "fd526e22-12ff-4fa0-a88d-7375c5d1e144"
        payload = json.loads(result.output)
        assert payload["uid"] == "fd526e22-12ff-4fa0-a88d-7375c5d1e144"
        assert payload["default_value"] == "hr88.cisco.com"
        assert len(payload["overrides"]) == 2
        assert len(payload["targets"]) == 2


class TestShowObjectValidation:
    """Tests for get command parameter validation."""

    def test_should_fail_when_uid_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)

        result = cli_runner.invoke(cli, ["objects", "show"])

        assert result.exit_code != 0
        assert "uid" in result.output.lower()


class TestShowObjectOutput:
    """Tests for get command output rendering."""

    def test_should_display_table_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_get(self: ObjectOverrideService, **kwargs: Any) -> ObjectDetailsResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "get_object", fake_get)

        result = cli_runner.invoke(
            cli,
            ["objects", "show", "--uid", "fd526e22-12ff-4fa0-a88d-7375c5d1e144"],
        )

        assert result.exit_code == 0
        assert "000_fqdn_fafa_renamed" in result.output
        assert "hr88.cisco.com" in result.output
        assert "Targets" in result.output
        assert "Overrides" in result.output
        assert "alex-fdm-template" in result.output

    def test_should_display_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_get(self: ObjectOverrideService, **kwargs: Any) -> ObjectDetailsResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "get_object", fake_get)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "show",
                "--uid",
                "fd526e22-12ff-4fa0-a88d-7375c5d1e144",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["object_type"] == "NETWORK_OBJECT"
        assert payload["overrides"][0]["target_id"] == "0b2f5a0d-6ccb-45e6-a65c-7d9dd48d7b55"
        assert payload["overrides"][0]["value"] == "11.10.11.122"

    def test_should_show_no_devices_message_when_no_targets(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_get(self: ObjectOverrideService, **kwargs: Any) -> ObjectDetailsResponse:
            return ObjectDetailsResponse(
                uid="obj-123",
                name="test-obj",
                description="",
                object_type="NETWORK_OBJECT",
                default_value="1.2.3.4",
                overrides=[],
                targets=[],
            )

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "get_object", fake_get)

        result = cli_runner.invoke(cli, ["objects", "show", "--uid", "obj-123"])

        assert result.exit_code == 0
        assert "No devices attached" in result.output
        assert "No overrides configured" in result.output


class TestObjectOverrideServiceGetObject:
    """Unit tests for ObjectOverrideService.get_object method."""

    def _make_response(self, data: dict[str, Any]) -> Mock:
        mock = Mock()
        mock.status = 200
        mock.read.return_value = json.dumps(data).encode("utf-8")
        return mock

    def test_should_return_full_object_details(self, monkeypatch: MonkeyPatch) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "fd526e22-12ff-4fa0-a88d-7375c5d1e144",
            "name": "000_fqdn_fafa_renamed",
            "description": None,
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "hr88.cisco.com"},
                "overrides": [
                    {
                        "targetId": "0b2f5a0d-6ccb-45e6-a65c-7d9dd48d7b55",
                        "content": {"literal": "11.10.11.122"},
                    },
                    {
                        "targetId": "897b293f-132e-4678-9d78-0f0947629500",
                        "content": {"literal": "11.14.11.14"},
                    },
                ],
            },
            "targets": [
                {
                    "id": "897b293f-132e-4678-9d78-0f0947629500",
                    "displayName": "alex-fdm-template",
                    "type": "FDM_MANAGED_FTD",
                },
                {
                    "id": "0b2f5a0d-6ccb-45e6-a65c-7d9dd48d7b55",
                    "displayName": "alex-fercal-crush-ftd-template",
                    "type": "FDM_MANAGED_FTD",
                },
            ],
        }
        mock_api.get_object_without_preload_content.return_value = self._make_response(raw_object)

        service = ObjectOverrideService.__new__(ObjectOverrideService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        result = service.get_object(uid="fd526e22-12ff-4fa0-a88d-7375c5d1e144")

        assert result.uid == "fd526e22-12ff-4fa0-a88d-7375c5d1e144"
        assert result.name == "000_fqdn_fafa_renamed"
        assert result.object_type == "NETWORK_OBJECT"
        assert result.default_value == "hr88.cisco.com"
        assert len(result.overrides) == 2
        assert result.overrides[0].target_id == "0b2f5a0d-6ccb-45e6-a65c-7d9dd48d7b55"
        assert result.overrides[0].value == "11.10.11.122"
        assert len(result.targets) == 2
        assert result.targets[0].display_name == "alex-fdm-template"

    def test_should_handle_object_with_no_overrides_or_targets(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "obj-123",
            "name": "simple-obj",
            "description": "a simple object",
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "10.0.0.1"},
            },
            "targets": [],
        }
        mock_api.get_object_without_preload_content.return_value = self._make_response(raw_object)

        service = ObjectOverrideService.__new__(ObjectOverrideService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        result = service.get_object(uid="obj-123")

        assert result.default_value == "10.0.0.1"
        assert result.description == "a simple object"
        assert result.overrides == []
        assert result.targets == []

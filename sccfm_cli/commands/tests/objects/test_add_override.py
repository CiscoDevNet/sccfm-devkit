# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk.exceptions import ApiException

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services.object_management import ObjectOverrideResponse, ObjectOverrideService
from sccfm_core.services.object_management.object_api_helper import ObjectApiHelper

SAMPLE_RESPONSE = ObjectOverrideResponse(
    uid="obj-123",
    name="test-object",
    object_type="NETWORK_OBJECT",
    overrides_count=1,
)


def _stub_init(self: ObjectOverrideService, config: Any) -> None:
    return None


class TestAddOverrideCommand:
    """Tests for the add-override command happy path."""

    def test_should_add_override_by_uid(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_add(self: ObjectOverrideService, **kwargs: Any) -> ObjectOverrideResponse:
            captured.update(kwargs)
            return SAMPLE_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "add_override", fake_add)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "add-override",
                "--uid",
                "obj-123",
                "--target-id",
                "device-456",
                "--override-value",
                "10.10.10.10",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert captured["uid"] == "obj-123"
        assert captured["target_id"] == "device-456"
        assert captured["override_value"] == "10.10.10.10"
        payload = json.loads(result.output)
        assert payload["uid"] == "obj-123"
        assert payload["overrides_count"] == 1


class TestAddOverrideValidation:
    """Tests for add-override command parameter validation."""

    def test_should_fail_when_uid_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "add-override",
                "--target-id",
                "device-456",
                "--override-value",
                "10.10.10.10",
            ],
        )

        assert result.exit_code != 0
        assert "--uid" in result.output or "uid" in result.output.lower()

    def test_should_fail_when_target_id_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "add-override",
                "--uid",
                "obj-123",
                "--override-value",
                "10.10.10.10",
            ],
        )

        assert result.exit_code != 0
        assert "target-id" in result.output or "target_id" in result.output

    def test_should_fail_when_override_value_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "add-override",
                "--uid",
                "obj-123",
                "--target-id",
                "device-456",
            ],
        )

        assert result.exit_code != 0
        assert "override-value" in result.output or "override_value" in result.output


class TestAddOverrideErrors:
    """Tests for add-override command error handling."""

    def test_should_fail_when_object_not_attached_to_device(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_add(self: ObjectOverrideService, **kwargs: Any) -> ObjectOverrideResponse:
            raise ValueError(
                "Object is not attached to any device; overrides require device attachment."
            )

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "add_override", fake_add)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "add-override",
                "--uid",
                "obj-123",
                "--target-id",
                "device-456",
                "--override-value",
                "10.10.10.10",
            ],
        )

        assert result.exit_code != 0
        assert "not attached" in result.output

    def test_should_display_api_error(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        error_body = json.dumps(
            {
                "errorMsg": "Object not found",
                "errorCode": "NOT_FOUND",
                "details": {},
            }
        )

        def fake_add(self: ObjectOverrideService, **kwargs: Any) -> ObjectOverrideResponse:
            raise ApiException(status=404, body=error_body)

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "add_override", fake_add)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "add-override",
                "--uid",
                "obj-123",
                "--target-id",
                "device-456",
                "--override-value",
                "10.10.10.10",
            ],
        )

        assert result.exit_code != 0
        assert "Object not found" in result.output or "NOT_FOUND" in result.output


class TestAddOverrideOutput:
    """Tests for add-override command output rendering."""

    def test_should_display_table_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_add(self: ObjectOverrideService, **kwargs: Any) -> ObjectOverrideResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "add_override", fake_add)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "add-override",
                "--uid",
                "obj-123",
                "--target-id",
                "device-456",
                "--override-value",
                "10.10.10.10",
            ],
        )

        assert result.exit_code == 0
        assert "Object Override" in result.output
        assert "obj-123" in result.output
        assert "Override added" in result.output

    def test_should_display_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_add(self: ObjectOverrideService, **kwargs: Any) -> ObjectOverrideResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "add_override", fake_add)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "add-override",
                "--uid",
                "obj-123",
                "--target-id",
                "device-456",
                "--override-value",
                "10.10.10.10",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["uid"] == "obj-123"
        assert payload["name"] == "test-object"
        assert payload["object_type"] == "NETWORK_OBJECT"
        assert payload["overrides_count"] == 1


class TestObjectOverrideService:
    """Unit tests for ObjectOverrideService.add_override method."""

    def _make_get_response(self, data: dict[str, Any]) -> Mock:
        mock = Mock()
        mock.status = 200
        mock.read.return_value = json.dumps(data).encode("utf-8")
        return mock

    def _make_patch_response(self, data: dict[str, Any]) -> Mock:
        mock = Mock()
        mock.status = 200
        mock.read.return_value = json.dumps(data).encode("utf-8")
        return mock

    def test_should_call_get_then_patch(self, monkeypatch: MonkeyPatch) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "targets": [{"uid": "device-456"}],
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "1.2.3.4"},
                "overrides": [],
            },
        }
        mock_api.get_object_without_preload_content.return_value = self._make_get_response(
            raw_object
        )

        patched_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "1.2.3.4"},
                "overrides": [{"targetId": "device-456", "content": {"literal": "10.10.10.10"}}],
            },
        }
        mock_api.modify_object_without_preload_content.return_value = self._make_patch_response(
            patched_object
        )

        service = ObjectOverrideService.__new__(ObjectOverrideService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        result = service.add_override(
            uid="obj-123",
            target_id="device-456",
            override_value="10.10.10.10",
        )

        assert result.uid == "obj-123"
        assert result.overrides_count == 1
        mock_api.get_object_without_preload_content.assert_called_once_with(uid="obj-123")
        mock_api.modify_object_without_preload_content.assert_called_once()
        call_kwargs = mock_api.modify_object_without_preload_content.call_args
        assert call_kwargs.kwargs["uid"] == "obj-123"

    def test_should_preserve_existing_overrides(self, monkeypatch: MonkeyPatch) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "targets": [{"uid": "device-111"}],
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "1.2.3.4"},
                "overrides": [{"targetId": "device-111", "content": {"literal": "5.5.5.5"}}],
            },
        }
        mock_api.get_object_without_preload_content.return_value = self._make_get_response(
            raw_object
        )

        patched_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "1.2.3.4"},
                "overrides": [
                    {"targetId": "device-111", "content": {"literal": "5.5.5.5"}},
                    {"targetId": "device-456", "content": {"literal": "10.10.10.10"}},
                ],
            },
        }
        mock_api.modify_object_without_preload_content.return_value = self._make_patch_response(
            patched_object
        )

        service = ObjectOverrideService.__new__(ObjectOverrideService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        result = service.add_override(
            uid="obj-123",
            target_id="device-456",
            override_value="10.10.10.10",
        )

        assert result.overrides_count == 2

        update_request = mock_api.modify_object_without_preload_content.call_args.kwargs[
            "update_request"
        ]
        assert update_request.value is not None
        assert len(update_request.value.overrides) == 2

    def test_should_raise_when_not_attached_to_device(self, monkeypatch: MonkeyPatch) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "targets": [],
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "1.2.3.4"},
                "overrides": [],
            },
        }
        mock_api.get_object_without_preload_content.return_value = self._make_get_response(
            raw_object
        )

        service = ObjectOverrideService.__new__(ObjectOverrideService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        with pytest.raises(ValueError, match="not attached to any device"):
            service.add_override(
                uid="obj-123",
                target_id="device-456",
                override_value="10.10.10.10",
            )

        mock_api.modify_object_without_preload_content.assert_not_called()

    def test_should_raise_for_unsupported_object_type(self, monkeypatch: MonkeyPatch) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "targets": [{"uid": "device-456"}],
            "value": {
                "objectType": "SERVICE_OBJECT",
                "defaultContent": {},
                "overrides": [],
            },
        }
        mock_api.get_object_without_preload_content.return_value = self._make_get_response(
            raw_object
        )

        service = ObjectOverrideService.__new__(ObjectOverrideService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        with pytest.raises(ValueError, match="not supported for object type"):
            service.add_override(
                uid="obj-123",
                target_id="device-456",
                override_value="10.10.10.10",
            )

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

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.models import Config
from cisco_sccfm_core.services.object_management import (
    ObjectOverrideResponse,
    ObjectOverrideService,
)
from cisco_sccfm_core.services.object_management.object_api_helper import ObjectApiHelper

SAMPLE_RESPONSE = ObjectOverrideResponse(
    uid="obj-123",
    name="test-object",
    object_type="NETWORK_OBJECT",
    overrides_count=1,
)


def _stub_init(self: ObjectOverrideService, config: Any) -> None:
    return None


class TestDeleteOverrideCommand:
    """Tests for the delete-override command happy path."""

    def test_should_delete_override(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_delete(self: ObjectOverrideService, **kwargs: Any) -> ObjectOverrideResponse:
            captured.update(kwargs)
            return SAMPLE_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "delete_override", fake_delete)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "delete-override",
                "--uid",
                "obj-123",
                "--target-id",
                "device-456",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert captured["uid"] == "obj-123"
        assert captured["target_id"] == "device-456"
        payload = json.loads(result.output)
        assert payload["uid"] == "obj-123"
        assert payload["overrides_count"] == 1


class TestDeleteOverrideValidation:
    """Tests for delete-override command parameter validation."""

    def test_should_fail_when_uid_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            ["objects", "delete-override", "--target-id", "device-456"],
        )

        assert result.exit_code != 0
        assert "uid" in result.output.lower()

    def test_should_fail_when_target_id_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            ["objects", "delete-override", "--uid", "obj-123"],
        )

        assert result.exit_code != 0
        assert "target-id" in result.output


class TestDeleteOverrideErrors:
    """Tests for delete-override command error handling."""

    def test_should_fail_when_override_not_found(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_delete(self: ObjectOverrideService, **kwargs: Any) -> ObjectOverrideResponse:
            raise ValueError("No override found for target ID 'device-456'.")

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "delete_override", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "delete-override", "--uid", "obj-123", "--target-id", "device-456"],
        )

        assert result.exit_code != 0
        assert "No override found" in result.output

    def test_should_display_api_error(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        error_body = json.dumps(
            {"errorMsg": "Object not found", "errorCode": "NOT_FOUND", "details": {}}
        )

        def fake_delete(self: ObjectOverrideService, **kwargs: Any) -> ObjectOverrideResponse:
            raise ApiException(status=404, body=error_body)

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "delete_override", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "delete-override", "--uid", "obj-123", "--target-id", "device-456"],
        )

        assert result.exit_code != 0
        assert "Object not found" in result.output or "NOT_FOUND" in result.output


class TestDeleteOverrideOutput:
    """Tests for delete-override command output rendering."""

    def test_should_display_table_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_delete(self: ObjectOverrideService, **kwargs: Any) -> ObjectOverrideResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "delete_override", fake_delete)

        result = cli_runner.invoke(
            cli,
            ["objects", "delete-override", "--uid", "obj-123", "--target-id", "device-456"],
        )

        assert result.exit_code == 0
        assert "Object Override" in result.output
        assert "obj-123" in result.output
        assert "deleted" in result.output.lower()

    def test_should_display_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_delete(self: ObjectOverrideService, **kwargs: Any) -> ObjectOverrideResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "delete_override", fake_delete)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "delete-override",
                "--uid",
                "obj-123",
                "--target-id",
                "device-456",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["uid"] == "obj-123"
        assert payload["overrides_count"] == 1


class TestObjectOverrideServiceDeleteOverride:
    """Unit tests for ObjectOverrideService.delete_override method."""

    def _make_response(self, data: dict[str, Any]) -> Mock:
        mock = Mock()
        mock.status = 200
        mock.read.return_value = json.dumps(data).encode("utf-8")
        return mock

    def test_should_delete_matching_override_and_preserve_others(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "1.2.3.4"},
                "overrides": [
                    {"targetId": "device-456", "content": {"literal": "5.5.5.5"}},
                    {"targetId": "device-789", "content": {"literal": "6.6.6.6"}},
                ],
            },
        }
        mock_api.get_object_without_preload_content.return_value = self._make_response(raw_object)

        patched_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "1.2.3.4"},
                "overrides": [
                    {"targetId": "device-789", "content": {"literal": "6.6.6.6"}},
                ],
            },
        }
        mock_api.modify_object_without_preload_content.return_value = self._make_response(
            patched_object
        )

        service = ObjectOverrideService.__new__(ObjectOverrideService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        result = service.delete_override(uid="obj-123", target_id="device-456")

        assert result.uid == "obj-123"
        assert result.overrides_count == 1

        update_request = mock_api.modify_object_without_preload_content.call_args.kwargs[
            "update_request"
        ]
        assert len(update_request.value.overrides) == 1
        remaining = update_request.value.overrides[0]
        assert remaining.target_id == "device-789"
        assert remaining.content.actual_instance.literal == "6.6.6.6"

    def test_should_send_null_overrides_when_last_override_deleted(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "1.2.3.4"},
                "overrides": [
                    {"targetId": "device-456", "content": {"literal": "5.5.5.5"}},
                ],
            },
        }
        mock_api.get_object_without_preload_content.return_value = self._make_response(raw_object)

        patched_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "1.2.3.4"},
            },
        }
        mock_api.modify_object_without_preload_content.return_value = self._make_response(
            patched_object
        )

        service = ObjectOverrideService.__new__(ObjectOverrideService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        result = service.delete_override(uid="obj-123", target_id="device-456")

        assert result.uid == "obj-123"
        assert result.overrides_count == 0

        update_request = mock_api.modify_object_without_preload_content.call_args.kwargs[
            "update_request"
        ]
        assert update_request.value.overrides is None

    def test_should_raise_when_override_not_found(self, monkeypatch: MonkeyPatch) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "1.2.3.4"},
                "overrides": [
                    {"targetId": "device-111", "content": {"literal": "5.5.5.5"}},
                ],
            },
        }
        mock_api.get_object_without_preload_content.return_value = self._make_response(raw_object)

        service = ObjectOverrideService.__new__(ObjectOverrideService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        with pytest.raises(ValueError, match="No override found for target ID 'device-999'"):
            service.delete_override(uid="obj-123", target_id="device-999")

        mock_api.modify_object_without_preload_content.assert_not_called()

    def test_should_raise_for_unsupported_object_type(self, monkeypatch: MonkeyPatch) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "value": {"objectType": "SERVICE_OBJECT", "defaultContent": {}, "overrides": []},
        }
        mock_api.get_object_without_preload_content.return_value = self._make_response(raw_object)

        service = ObjectOverrideService.__new__(ObjectOverrideService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        with pytest.raises(ValueError, match="not supported for object type"):
            service.delete_override(uid="obj-123", target_id="device-456")

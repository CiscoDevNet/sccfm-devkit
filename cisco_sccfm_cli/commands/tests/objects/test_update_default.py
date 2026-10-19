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
    ObjectOverrideService,
    UpdateDefaultValueResponse,
)
from cisco_sccfm_core.services.object_management.object_api_helper import ObjectApiHelper

SAMPLE_RESPONSE = UpdateDefaultValueResponse(
    uid="obj-123",
    name="test-object",
    object_type="NETWORK_OBJECT",
    default_value="10.10.10.10",
)


def _stub_init(self: ObjectOverrideService, config: Any) -> None:
    return None


class TestUpdateDefaultCommand:
    """Tests for the update-default command happy path."""

    def test_should_update_default_value(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_update(self: ObjectOverrideService, **kwargs: Any) -> UpdateDefaultValueResponse:
            captured.update(kwargs)
            return SAMPLE_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "update_default_value", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "update-default",
                "--uid",
                "obj-123",
                "--value",
                "10.10.10.10",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert captured["uid"] == "obj-123"
        assert captured["new_value"] == "10.10.10.10"
        payload = json.loads(result.output)
        assert payload["uid"] == "obj-123"
        assert payload["default_value"] == "10.10.10.10"


class TestUpdateDefaultValidation:
    """Tests for update-default command parameter validation."""

    def test_should_fail_when_uid_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)

        result = cli_runner.invoke(cli, ["objects", "update-default", "--value", "10.10.10.10"])

        assert result.exit_code != 0
        assert "uid" in result.output.lower()

    def test_should_fail_when_value_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)

        result = cli_runner.invoke(cli, ["objects", "update-default", "--uid", "obj-123"])

        assert result.exit_code != 0
        assert "value" in result.output.lower()


class TestUpdateDefaultErrors:
    """Tests for update-default command error handling."""

    def test_should_fail_for_unsupported_object_type(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_update(self: ObjectOverrideService, **kwargs: Any) -> UpdateDefaultValueResponse:
            raise ValueError(
                "Updating default value is not supported for object type 'SERVICE_OBJECT'."
            )

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "update_default_value", fake_update)

        result = cli_runner.invoke(
            cli,
            ["objects", "update-default", "--uid", "obj-123", "--value", "10.10.10.10"],
        )

        assert result.exit_code != 0
        assert "not supported" in result.output

    def test_should_display_api_error(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        error_body = json.dumps(
            {"errorMsg": "Object not found", "errorCode": "NOT_FOUND", "details": {}}
        )

        def fake_update(self: ObjectOverrideService, **kwargs: Any) -> UpdateDefaultValueResponse:
            raise ApiException(status=404, body=error_body)

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "update_default_value", fake_update)

        result = cli_runner.invoke(
            cli,
            ["objects", "update-default", "--uid", "obj-123", "--value", "10.10.10.10"],
        )

        assert result.exit_code != 0
        assert "Object not found" in result.output or "NOT_FOUND" in result.output


class TestUpdateDefaultOutput:
    """Tests for update-default command output rendering."""

    def test_should_display_table_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_update(self: ObjectOverrideService, **kwargs: Any) -> UpdateDefaultValueResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "update_default_value", fake_update)

        result = cli_runner.invoke(
            cli,
            ["objects", "update-default", "--uid", "obj-123", "--value", "10.10.10.10"],
        )

        assert result.exit_code == 0
        assert "Object Default" in result.output
        assert "obj-123" in result.output
        assert "Default value updated" in result.output

    def test_should_display_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_update(self: ObjectOverrideService, **kwargs: Any) -> UpdateDefaultValueResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "update_default_value", fake_update)

        result = cli_runner.invoke(
            cli,
            [
                "objects",
                "update-default",
                "--uid",
                "obj-123",
                "--value",
                "10.10.10.10",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["uid"] == "obj-123"
        assert payload["default_value"] == "10.10.10.10"
        assert payload["object_type"] == "NETWORK_OBJECT"


class TestObjectOverrideServiceUpdateDefault:
    """Unit tests for ObjectOverrideService.update_default_value method."""

    def _make_response(self, data: dict[str, Any]) -> Mock:
        mock = Mock()
        mock.status = 200
        mock.read.return_value = json.dumps(data).encode("utf-8")
        return mock

    def test_should_update_default_and_preserve_overrides(self, monkeypatch: MonkeyPatch) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "targets": [{"id": "device-456"}],
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
                "defaultContent": {"literal": "10.10.10.10"},
                "overrides": [
                    {"targetId": "device-456", "content": {"literal": "5.5.5.5"}},
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

        result = service.update_default_value(uid="obj-123", new_value="10.10.10.10")

        assert result.uid == "obj-123"
        assert result.default_value == "10.10.10.10"

        update_request = mock_api.modify_object_without_preload_content.call_args.kwargs[
            "update_request"
        ]
        assert update_request.value is not None
        assert len(update_request.value.overrides) == 2

    def test_should_update_default_when_no_overrides(self, monkeypatch: MonkeyPatch) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "1.2.3.4"},
                "overrides": [],
            },
        }
        mock_api.get_object_without_preload_content.return_value = self._make_response(raw_object)

        patched_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "10.10.10.10"},
            },
        }
        mock_api.modify_object_without_preload_content.return_value = self._make_response(
            patched_object
        )

        service = ObjectOverrideService.__new__(ObjectOverrideService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        result = service.update_default_value(uid="obj-123", new_value="10.10.10.10")

        assert result.default_value == "10.10.10.10"

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
            service.update_default_value(uid="obj-123", new_value="10.10.10.10")

        mock_api.modify_object_without_preload_content.assert_not_called()

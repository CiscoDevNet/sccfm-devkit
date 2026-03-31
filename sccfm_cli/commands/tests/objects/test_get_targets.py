from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services.object_management import (
    ObjectOverrideService,
    ObjectTargetItem,
    ObjectTargetsResponse,
)
from sccfm_core.services.object_management.object_api_helper import ObjectApiHelper

SAMPLE_TARGETS_RESPONSE = ObjectTargetsResponse(
    uid="obj-123",
    name="test-object",
    targets=[
        ObjectTargetItem(id="device-456", display_name="Branch ASA", type="ASA"),
        ObjectTargetItem(id="device-789", display_name="HQ FTD", type="CDFMC_MANAGED_FTD"),
    ],
)

EMPTY_TARGETS_RESPONSE = ObjectTargetsResponse(
    uid="obj-123",
    name="test-object",
    targets=[],
)


def _stub_init(self: ObjectOverrideService, config: Any) -> None:
    return None


class TestGetTargetsCommand:
    """Tests for the get-targets command happy path."""

    def test_should_return_targets_for_object(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_get_targets(self: ObjectOverrideService, **kwargs: Any) -> ObjectTargetsResponse:
            captured.update(kwargs)
            return SAMPLE_TARGETS_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "get_targets", fake_get_targets)

        result = cli_runner.invoke(
            cli,
            ["objects", "get-targets", "--uid", "obj-123", "--format", "json"],
        )

        assert result.exit_code == 0
        assert captured["uid"] == "obj-123"
        payload = json.loads(result.output)
        assert payload["uid"] == "obj-123"
        assert len(payload["targets"]) == 2
        assert payload["targets"][0]["id"] == "device-456"
        assert payload["targets"][0]["display_name"] == "Branch ASA"
        assert payload["targets"][0]["type"] == "ASA"


class TestGetTargetsValidation:
    """Tests for get-targets command parameter validation."""

    def test_should_fail_when_uid_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)

        result = cli_runner.invoke(cli, ["objects", "get-targets"])

        assert result.exit_code != 0
        assert "uid" in result.output.lower()


class TestGetTargetsOutput:
    """Tests for get-targets command output rendering."""

    def test_should_display_table_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_get_targets(self: ObjectOverrideService, **kwargs: Any) -> ObjectTargetsResponse:
            return SAMPLE_TARGETS_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "get_targets", fake_get_targets)

        result = cli_runner.invoke(cli, ["objects", "get-targets", "--uid", "obj-123"])

        assert result.exit_code == 0
        assert "device-456" in result.output
        assert "Branch ASA" in result.output
        assert "ASA" in result.output

    def test_should_display_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_get_targets(self: ObjectOverrideService, **kwargs: Any) -> ObjectTargetsResponse:
            return SAMPLE_TARGETS_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "get_targets", fake_get_targets)

        result = cli_runner.invoke(
            cli, ["objects", "get-targets", "--uid", "obj-123", "--format", "json"]
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["uid"] == "obj-123"
        assert len(payload["targets"]) == 2

    def test_should_display_warning_when_no_targets(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_get_targets(self: ObjectOverrideService, **kwargs: Any) -> ObjectTargetsResponse:
            return EMPTY_TARGETS_RESPONSE

        monkeypatch.setattr(ObjectOverrideService, "__init__", _stub_init)
        monkeypatch.setattr(ObjectOverrideService, "get_targets", fake_get_targets)

        result = cli_runner.invoke(cli, ["objects", "get-targets", "--uid", "obj-123"])

        assert result.exit_code == 0
        assert "not attached" in result.output


class TestObjectOverrideServiceGetTargets:
    """Unit tests for ObjectOverrideService.get_targets method."""

    def test_should_return_targets_from_api(self, monkeypatch: MonkeyPatch) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "targets": [
                {"id": "device-456", "displayName": "Branch ASA", "type": "ASA"},
                {"id": "device-789", "displayName": "HQ FTD", "type": "CDFMC_MANAGED_FTD"},
            ],
            "value": {
                "objectType": "NETWORK_OBJECT",
                "defaultContent": {"literal": "1.2.3.4"},
            },
        }
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(raw_object).encode("utf-8")
        mock_api.get_object_without_preload_content.return_value = mock_response

        service = ObjectOverrideService.__new__(ObjectOverrideService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        result = service.get_targets(uid="obj-123")

        assert result.uid == "obj-123"
        assert result.name == "test-obj"
        assert len(result.targets) == 2
        assert result.targets[0].id == "device-456"
        assert result.targets[0].display_name == "Branch ASA"
        assert result.targets[0].type == "ASA"
        mock_api.get_object_without_preload_content.assert_called_once_with(uid="obj-123")

    def test_should_return_empty_targets_when_none_attached(self, monkeypatch: MonkeyPatch) -> None:
        mock_api = Mock()

        raw_object = {
            "uid": "obj-123",
            "name": "test-obj",
            "targets": [],
            "value": {"objectType": "NETWORK_OBJECT", "defaultContent": {"literal": "1.2.3.4"}},
        }
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(raw_object).encode("utf-8")
        mock_api.get_object_without_preload_content.return_value = mock_response

        service = ObjectOverrideService.__new__(ObjectOverrideService)
        service._helper = ObjectApiHelper.__new__(ObjectApiHelper)
        service._object_api = mock_api

        result = service.get_targets(uid="obj-123")

        assert result.targets == []

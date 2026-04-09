from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services.policy.access_group_service import (
    AccessGroupListResponse,
    AccessGroupResponse,
    AccessGroupService,
)

SAMPLE_RESPONSE = AccessGroupResponse(
    uid="ag-uid-123",
    name="outside_access_in",
    entity_uid="device-uid-456",
    is_shared=False,
    shared_access_group_uid=None,
    applied_to=["device-uid-456"],
    resources=[{"interfaceName": "outside", "direction": "IN"}],
    created_date="2026-01-01T00:00:00Z",
    updated_date=None,
)

SAMPLE_LIST = AccessGroupListResponse(
    count=2,
    items=[
        SAMPLE_RESPONSE,
        AccessGroupResponse(
            uid="ag-uid-789",
            name="inside_access_out",
            entity_uid="device-uid-456",
            is_shared=True,
            shared_access_group_uid="shared-uid-001",
            applied_to=None,
            resources=None,
            created_date="2026-02-01T00:00:00Z",
            updated_date=None,
        ),
    ],
    limit=50,
    offset=0,
)


def _stub_init(self: AccessGroupService, config: Any) -> None:
    return None


class TestGetAccessGroup:
    def test_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_fetch(self: AccessGroupService, **kwargs: Any) -> AccessGroupResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(AccessGroupService, "__init__", _stub_init)
        monkeypatch.setattr(AccessGroupService, "fetch_access_group", fake_fetch)

        result = cli_runner.invoke(
            cli,
            ["policies", "access-group", "get", "--uid", "ag-uid-123", "--format", "json"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["uid"] == "ag-uid-123"
        assert payload["name"] == "outside_access_in"

    def test_table_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_fetch(self: AccessGroupService, **kwargs: Any) -> AccessGroupResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(AccessGroupService, "__init__", _stub_init)
        monkeypatch.setattr(AccessGroupService, "fetch_access_group", fake_fetch)

        result = cli_runner.invoke(
            cli,
            ["policies", "access-group", "get", "--uid", "ag-uid-123", "--format", "table"],
        )

        assert result.exit_code == 0
        assert "outside_access_in" in result.output


class TestListAccessGroup:
    def test_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_list(self: AccessGroupService, **kwargs: Any) -> AccessGroupListResponse:
            return SAMPLE_LIST

        monkeypatch.setattr(AccessGroupService, "__init__", _stub_init)
        monkeypatch.setattr(AccessGroupService, "list_access_groups", fake_list)

        result = cli_runner.invoke(
            cli,
            ["policies", "access-group", "list", "--format", "json"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["count"] == 2
        assert len(payload["items"]) == 2

    def test_table_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_list(self: AccessGroupService, **kwargs: Any) -> AccessGroupListResponse:
            return SAMPLE_LIST

        monkeypatch.setattr(AccessGroupService, "__init__", _stub_init)
        monkeypatch.setattr(AccessGroupService, "list_access_groups", fake_list)

        result = cli_runner.invoke(
            cli,
            ["policies", "access-group", "list", "--format", "table"],
        )

        assert result.exit_code == 0
        assert "outside_access_in" in result.output
        assert "inside_access_out" in result.output

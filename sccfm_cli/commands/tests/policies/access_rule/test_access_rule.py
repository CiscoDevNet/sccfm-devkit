from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services import NetworkObjectService
from sccfm_core.services.object_management import NetworkObjectResponse
from sccfm_core.services.policy.access_rule_service import (
    AccessRuleListResponse,
    AccessRuleResponse,
    AccessRuleService,
)

SAMPLE_RESPONSE = AccessRuleResponse(
    uid="rule-uid-123",
    access_group_uid="ag-uid-456",
    entity_uid="device-uid-789",
    index=1,
    is_active_rule=True,
    rule_action="PERMIT",
    rule_type="L3",
    remark="Allow web traffic",
    source_network={"name": "web-servers", "uid": "net-uid-1", "type": "NETWORK_OBJECT"},
    destination_network={"name": "db-servers", "uid": "net-uid-2", "type": "NETWORK_OBJECT"},
    protocol={"name": "tcp"},
    source_port=None,
    destination_port={"name": "443"},
    log_settings=None,
    rule_configuration_text=None,
    created_date="2026-01-01T00:00:00Z",
    updated_date=None,
)


def _stub_init(self: AccessRuleService, config: Any) -> None:
    return None


def _stub_network_object_init(self: NetworkObjectService, config: Any) -> None:
    return None


class TestCreateAccessRule:
    def test_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_create(self: AccessRuleService, **kwargs: Any) -> AccessRuleResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(AccessRuleService, "__init__", _stub_init)
        monkeypatch.setattr(AccessRuleService, "create_access_rule", fake_create)

        result = cli_runner.invoke(
            cli,
            [
                "policies",
                "access-rule",
                "create",
                "--access-group-uid",
                "ag-uid-456",
                "--entity-uid",
                "device-uid-789",
                "--index",
                "1",
                "--rule-action",
                "PERMIT",
                "--source-network",
                "web-servers",
                "--destination-network",
                "db-servers",
                "--protocol",
                "tcp",
                "--destination-port",
                "443",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["uid"] == "rule-uid-123"
        assert payload["rule_action"] == "PERMIT"

    def test_table_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_create(self: AccessRuleService, **kwargs: Any) -> AccessRuleResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(AccessRuleService, "__init__", _stub_init)
        monkeypatch.setattr(AccessRuleService, "create_access_rule", fake_create)

        result = cli_runner.invoke(
            cli,
            [
                "policies",
                "access-rule",
                "create",
                "--access-group-uid",
                "ag-uid-456",
                "--entity-uid",
                "device-uid-789",
                "--index",
                "1",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 0
        assert "Access rule created" in result.output


class TestCheck:
    def test_json_output_when_references_exist(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        create_called = {"called": False}

        def fake_get_by_name(self: NetworkObjectService, name: str) -> NetworkObjectResponse | None:
            return NetworkObjectResponse(
                uid=f"uid-{name}",
                name=name,
                description=None,
                elements=[],
                labels=[],
                tags={},
                object_type="NETWORK_OBJECT",
                literal="10.0.0.0/24",
            )

        def fake_create(self: AccessRuleService, **kwargs: Any) -> AccessRuleResponse:
            create_called["called"] = True
            return SAMPLE_RESPONSE

        monkeypatch.setattr(AccessRuleService, "__init__", _stub_init)
        monkeypatch.setattr(AccessRuleService, "create_access_rule", fake_create)
        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_network_object_init)
        monkeypatch.setattr(NetworkObjectService, "get_network_object_by_name", fake_get_by_name)

        result = cli_runner.invoke(
            cli,
            [
                "policies",
                "access-rule",
                "create",
                "--access-group-uid",
                "ag-uid-456",
                "--entity-uid",
                "device-uid-789",
                "--index",
                "1",
                "--source-network",
                "web-servers",
                "--destination-network",
                "db-servers",
                "--check",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert create_called["called"] is False
        payload = json.loads(result.output)
        assert payload["operation"] == "create"
        assert payload["can_proceed"] is True
        assert payload["reason"] == "network_references_resolved"
        assert len(payload["network_references"]) == 2
        assert payload["network_references"][0]["entity_type"] == "Source network object"
        assert payload["network_references"][1]["entity_type"] == "Destination network object"

    def test_table_output_when_reference_missing(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        create_called = {"called": False}

        def fake_get_by_name(self: NetworkObjectService, name: str) -> NetworkObjectResponse | None:
            if name == "missing-dst":
                return None
            return NetworkObjectResponse(
                uid="uid-web-servers",
                name=name,
                description=None,
                elements=[],
                labels=[],
                tags={},
                object_type="NETWORK_OBJECT",
                literal="10.0.0.0/24",
            )

        def fake_create(self: AccessRuleService, **kwargs: Any) -> AccessRuleResponse:
            create_called["called"] = True
            return SAMPLE_RESPONSE

        monkeypatch.setattr(AccessRuleService, "__init__", _stub_init)
        monkeypatch.setattr(AccessRuleService, "create_access_rule", fake_create)
        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_network_object_init)
        monkeypatch.setattr(NetworkObjectService, "get_network_object_by_name", fake_get_by_name)

        result = cli_runner.invoke(
            cli,
            [
                "policies",
                "access-rule",
                "create",
                "--access-group-uid",
                "ag-uid-456",
                "--entity-uid",
                "device-uid-789",
                "--index",
                "1",
                "--source-network",
                "web-servers",
                "--destination-network",
                "missing-dst",
                "--check",
            ],
        )

        assert result.exit_code == 0
        assert create_called["called"] is False
        assert "create would fail" in result.output
        assert "Source network object" in result.output
        assert "missing-dst" in result.output
        assert "not found" in result.output

    def test_check_no_networks_succeeds(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """--check with no network references should pass with no_network_references."""
        create_called = {"called": False}

        def fake_create(self: AccessRuleService, **kwargs: Any) -> AccessRuleResponse:
            create_called["called"] = True
            return SAMPLE_RESPONSE

        monkeypatch.setattr(AccessRuleService, "__init__", _stub_init)
        monkeypatch.setattr(AccessRuleService, "create_access_rule", fake_create)
        monkeypatch.setattr(NetworkObjectService, "__init__", _stub_network_object_init)

        result = cli_runner.invoke(
            cli,
            [
                "policies",
                "access-rule",
                "create",
                "--access-group-uid",
                "ag-uid-456",
                "--entity-uid",
                "device-uid-789",
                "--index",
                "1",
                "--check",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert create_called["called"] is False
        payload = json.loads(result.output)
        assert payload["can_proceed"] is True
        assert payload["reason"] == "no_network_references"
        assert payload["network_references"] == []


SAMPLE_LIST_RESPONSE = AccessRuleListResponse(
    count=2,
    items=[SAMPLE_RESPONSE, SAMPLE_RESPONSE],
    limit=50,
    offset=0,
)


class TestGetAccessRule:
    def test_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_fetch(self: AccessRuleService, **kwargs: Any) -> AccessRuleResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(AccessRuleService, "__init__", _stub_init)
        monkeypatch.setattr(AccessRuleService, "fetch_access_rule", fake_fetch)

        result = cli_runner.invoke(
            cli,
            [
                "policies",
                "access-rule",
                "get",
                "--uid",
                "rule-uid-123",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["uid"] == "rule-uid-123"
        assert payload["rule_action"] == "PERMIT"

    def test_table_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_fetch(self: AccessRuleService, **kwargs: Any) -> AccessRuleResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(AccessRuleService, "__init__", _stub_init)
        monkeypatch.setattr(AccessRuleService, "fetch_access_rule", fake_fetch)

        result = cli_runner.invoke(
            cli,
            [
                "policies",
                "access-rule",
                "get",
                "--uid",
                "rule-uid-123",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 0
        assert "rule-uid-123" in result.output


class TestListAccessRule:
    def test_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_list(self: AccessRuleService, **kwargs: Any) -> AccessRuleListResponse:
            return SAMPLE_LIST_RESPONSE

        monkeypatch.setattr(AccessRuleService, "__init__", _stub_init)
        monkeypatch.setattr(AccessRuleService, "list_access_rules", fake_list)

        result = cli_runner.invoke(
            cli,
            [
                "policies",
                "access-rule",
                "list",
                "--format",
                "json",
            ],
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
        def fake_list(self: AccessRuleService, **kwargs: Any) -> AccessRuleListResponse:
            return SAMPLE_LIST_RESPONSE

        monkeypatch.setattr(AccessRuleService, "__init__", _stub_init)
        monkeypatch.setattr(AccessRuleService, "list_access_rules", fake_list)

        result = cli_runner.invoke(
            cli,
            [
                "policies",
                "access-rule",
                "list",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 0
        assert "Number of entries:" in result.output
        assert "Page:" in result.output
        assert "Access Rules" in result.output


class TestUpdateAccessRule:
    def test_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_modify(self: AccessRuleService, **kwargs: Any) -> AccessRuleResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(AccessRuleService, "__init__", _stub_init)
        monkeypatch.setattr(AccessRuleService, "modify_access_rule", fake_modify)

        result = cli_runner.invoke(
            cli,
            [
                "policies",
                "access-rule",
                "update",
                "--uid",
                "rule-uid-123",
                "--remark",
                "Updated remark",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["uid"] == "rule-uid-123"

    def test_table_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_modify(self: AccessRuleService, **kwargs: Any) -> AccessRuleResponse:
            return SAMPLE_RESPONSE

        monkeypatch.setattr(AccessRuleService, "__init__", _stub_init)
        monkeypatch.setattr(AccessRuleService, "modify_access_rule", fake_modify)

        result = cli_runner.invoke(
            cli,
            [
                "policies",
                "access-rule",
                "update",
                "--uid",
                "rule-uid-123",
                "--rule-action",
                "DENY",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 0
        assert "Access rule updated" in result.output

    def test_fails_without_update_fields(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(AccessRuleService, "__init__", _stub_init)

        result = cli_runner.invoke(
            cli,
            [
                "policies",
                "access-rule",
                "update",
                "--uid",
                "rule-uid-123",
            ],
        )

        assert result.exit_code != 0
        assert "At least one update field" in result.output


class TestDeleteAccessRule:
    def test_delete_success(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        def fake_delete(self: AccessRuleService, **kwargs: Any) -> str:
            return "rule-uid-123"

        monkeypatch.setattr(AccessRuleService, "__init__", _stub_init)
        monkeypatch.setattr(AccessRuleService, "delete_access_rule", fake_delete)

        result = cli_runner.invoke(
            cli,
            [
                "policies",
                "access-rule",
                "delete",
                "--uid",
                "rule-uid-123",
            ],
        )

        assert result.exit_code == 0
        assert "Access rule deleted" in result.output
        assert "rule-uid-123" in result.output

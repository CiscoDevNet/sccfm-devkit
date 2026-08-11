# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import shlex
import tomllib
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Any

import click
import pytest
from click.testing import CliRunner

from cisco_sccfm_cli import schema as schema_module
from cisco_sccfm_cli.cli import cli


def test_package_version_should_prefer_installed_distribution_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def installed_version(distribution_name: str) -> str:
        assert distribution_name == "cisco-sccfm-devkit"
        return "9.8.7"

    def source_version() -> str | None:
        return "1.2.3"

    monkeypatch.setattr(schema_module, "version", installed_version)
    monkeypatch.setattr(schema_module, "_pyproject_version", source_version)

    assert schema_module._package_version() == "9.8.7"


def test_package_version_should_fall_back_to_source_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_version(distribution_name: str) -> str:
        assert distribution_name == "cisco-sccfm-devkit"
        raise PackageNotFoundError(distribution_name)

    def source_version() -> str | None:
        return "1.2.3"

    monkeypatch.setattr(schema_module, "version", missing_version)
    monkeypatch.setattr(schema_module, "_pyproject_version", source_version)

    assert schema_module._package_version() == "1.2.3"


def test_package_version_should_report_unknown_without_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_version(distribution_name: str) -> str:
        assert distribution_name == "cisco-sccfm-devkit"
        raise PackageNotFoundError(distribution_name)

    def source_version() -> str | None:
        return None

    monkeypatch.setattr(schema_module, "version", missing_version)
    monkeypatch.setattr(schema_module, "_pyproject_version", source_version)

    assert schema_module._package_version() == "unknown"


def test_schema_export_should_emit_machine_readable_command_tree(
    cli_runner: CliRunner,
) -> None:
    result = cli_runner.invoke(
        cli,
        ["schema", "export", "--format", "json"],
        prog_name="sccfm-cli",
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)

    assert payload["schema_version"] == "1.0"
    assert payload["tool_name"] == "sccfm-cli"
    assert payload["application"] == "sccfm-cli"
    assert payload["version"] == _project_version()
    assert payload["generated_at"]
    assert _option(payload["global_options"], "profile")["default"] == "default"
    assert _option(payload["global_options"], "profile")["scope"] == "global"
    assert _option(payload["global_options"], "profile")["placement"] == "before_command_path"

    commands = _commands_by_name(payload)
    assert "sccfm-cli schema export" in commands
    assert "sccfm-cli inventory devices asa upgrade trigger" in commands
    assert "sccfm-cli configure" in commands
    assert any(command["kind"] == "group" for command in payload["command_tree"])
    assert all(command["kind"] == "command" for command in payload["commands"])


def test_schema_export_should_describe_options_and_auth_requirements(
    cli_runner: CliRunner,
) -> None:
    result = cli_runner.invoke(cli, ["schema", "export"], prog_name="sccfm-cli")
    assert result.exit_code == 0, result.output

    commands = _commands_by_name(json.loads(result.output))
    configure = commands["sccfm-cli configure"]
    region = _option(configure["options"], "region")
    api_token = _option(configure["options"], "api_token")

    assert configure["readonly"] is True
    assert configure["side_effects"] == [
        "Writes the selected profile to the local sccfm-cli configuration file."
    ]
    assert configure["auth"]["mode"] == "none"
    assert configure["auth"]["requires_profile"] is False
    assert region["type"] == "choice"
    assert "us" in region["values"]
    assert region["required"] is True
    assert api_token["required"] is False
    assert api_token["sensitive"] is True
    assert api_token["envvar"] == "SCCFM_API_TOKEN"
    assert "--api-token" not in configure["examples"][1]
    assert "--region int" in configure["examples"][1]

    status = commands["sccfm-cli status"]
    assert status["auth"]["mode"] == "sccfm_profile"
    assert status["auth"]["requires_profile"] is True
    assert status["auth"]["requires_api_token"] is True


def test_schema_export_should_include_mutation_and_handler_constraints(
    cli_runner: CliRunner,
) -> None:
    result = cli_runner.invoke(cli, ["schema", "export"], prog_name="sccfm-cli")
    assert result.exit_code == 0, result.output

    commands = _commands_by_name(json.loads(result.output))
    asa_cli = commands["sccfm-cli inventory devices asa cli execute"]
    ftd_cli = commands["sccfm-cli inventory devices cdfmc-managed-ftd cli execute"]
    ftd_onboard = commands["sccfm-cli inventory devices cdfmc-managed-ftd onboard"]
    network_update = commands["sccfm-cli objects network update"]
    smartlicense = commands["sccfm-cli inventory devices asa smartlicense"]

    assert asa_cli["readonly"] is False
    assert asa_cli["side_effects"] == [
        "May change state in SCC Firewall Manager or on managed devices."
    ]
    assert ftd_cli["readonly"] is True
    assert _constraint(ftd_cli["constraints"], "value_prefix") == {
        "type": "value_prefix",
        "option": "command",
        "prefix": "show",
        "case_sensitive": False,
        "description": "--command must be 'show' or start with 'show '.",
    }

    asa_constraints = asa_cli["constraints"]
    asa_option_groups = asa_cli["option_groups"]
    assert _constraint(asa_constraints, "mutually_exclusive")["options"] == [
        "device_name",
        "query",
        "device_uids",
    ]
    assert (
        _option_group(asa_option_groups, "device_name_or_query_or_device_uids")[
            "mutually_exclusive"
        ]
        is True
    )
    assert _constraint(asa_constraints, "exactly_one_unless")["options"] == [
        "script",
        "script_file",
    ]
    assert "--device-name <device-name>" in asa_cli["examples"][1]
    assert "--script <script>" in asa_cli["examples"][1]

    assert _constraint(network_update["constraints"], "mutually_exclusive")["options"] == [
        "uid",
        "name",
    ]
    assert (
        _option_group(network_update["option_groups"], "uid_or_name")["mutually_exclusive"] is True
    )
    assert _constraint(network_update["constraints"], "requires_any")["description"] == (
        "At least one update field must be provided."
    )
    assert _constraint(smartlicense["constraints"], "required_unless")["options"] == [
        "feature_tier",
    ]
    smartlicense_token = _option(smartlicense["options"], "token")
    smartlicense_token_file = _option(smartlicense["options"], "token_file")
    token_source_constraint = _constraint_for_options(
        smartlicense["constraints"],
        "mutually_exclusive",
        ["token", "token_file"],
    )
    assert smartlicense_token["sensitive"] is True
    assert smartlicense_token["envvar"] == "SCCFM_SMART_LICENSE_TOKEN"
    assert smartlicense_token_file["type"] == "path"
    assert token_source_constraint["min_required"] == 0
    assert token_source_constraint["max_allowed"] == 1
    assert "--token" not in smartlicense["examples"][1]
    assert "--token-file" not in smartlicense["examples"][1]
    assert "--feature-tier standard" in smartlicense["examples"][1]
    ftd_virtual_dependency = _constraint(ftd_onboard["constraints"], "depends_on")
    assert ftd_virtual_dependency["option"] == "virtual"
    assert ftd_virtual_dependency["requires"] == "performance_tier"


def test_schema_export_should_avoid_duplicate_or_misleading_fields(
    cli_runner: CliRunner,
) -> None:
    result = cli_runner.invoke(cli, ["schema", "export"], prog_name="sccfm-cli")
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)

    for command in payload["commands"]:
        assert "mutating" not in command
        assert "mutates_sccfm" not in command
        assert "auth_requirements" not in command
        assert "display_option_groups" not in command
        for option in command["options"]:
            assert "allowed_values" not in option
            assert "option_group" not in option

    asa_onboard = _commands_by_name(payload)["sccfm-cli inventory devices asa onboard"]
    connector_name = _constraint(asa_onboard["constraints"], "required_when")
    assert connector_name["option"] == "connector_name"
    assert connector_name["when"] == {"option": "connector_type", "equals": "SDC"}

    readonly_by_name = {command["command"]: command["readonly"] for command in payload["commands"]}
    assert readonly_by_name["sccfm-cli inventory devices cdfmc-managed-ftd cli execute"] is True
    assert readonly_by_name["sccfm-cli inventory devices asa cli execute"] is False


def test_schema_export_should_include_option_aliases_defaults_and_ranges(
    cli_runner: CliRunner,
) -> None:
    result = cli_runner.invoke(cli, ["schema", "export"], prog_name="sccfm-cli")
    assert result.exit_code == 0, result.output

    commands = _commands_by_name(json.loads(result.output))
    trigger = commands["sccfm-cli inventory devices asa upgrade trigger"]

    assert trigger["readonly"] is False
    wait = _option(trigger["options"], "wait")
    timeout = _option(trigger["options"], "timeout")
    output_format = _option(trigger["options"], "format")

    assert wait["aliases"] == ["--wait", "--no-wait"]
    assert wait["scope"] == "command"
    assert wait["placement"] == "after_command_path"
    assert wait["default"] is False
    assert timeout["type"] == "integer"
    assert timeout["value_constraints"]["min"] == 1
    assert output_format["values"] == ["table", "json"]
    assert trigger["examples"][0] == "sccfm-cli inventory devices asa upgrade trigger --help"


def test_schema_export_should_include_queryable_field_metadata(
    cli_runner: CliRunner,
) -> None:
    result = cli_runner.invoke(cli, ["schema", "export"], prog_name="sccfm-cli")
    assert result.exit_code == 0, result.output

    commands = _commands_by_name(json.loads(result.output))
    asa_list = commands["sccfm-cli inventory devices asa list"]
    online_field = _field(asa_list["queryable_fields"], "connectivityState")
    device_type_field = _field(asa_list["queryable_fields"], "deviceType")

    assert online_field["values"]
    assert "ONLINE" in online_field["values"]
    assert "connectivityState:ONLINE" in online_field["examples"]
    assert "online" in online_field["natural_language_aliases"]
    assert "ASA" in device_type_field["values"]
    assert asa_list["field_notes"] == [
        (
            "This command automatically adds its deviceType filter. Do not add a "
            "deviceType clause unless the user explicitly asks for a different filter."
        ),
        "Translate 'online' to connectivityState:ONLINE.",
    ]


def test_schema_export_should_write_json_to_output_file(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "schema.json"

    result = cli_runner.invoke(
        cli,
        ["schema", "export", "--output", str(output_path)],
        prog_name="sccfm-cli",
    )

    assert result.exit_code == 0, result.output
    assert result.output == ""

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    commands = _commands_by_name(payload)
    output = _option(commands["sccfm-cli schema export"]["options"], "output")

    assert payload["tool_name"] == "sccfm-cli"
    assert output["aliases"] == ["--output", "-o"]
    assert output["type"] == "path"
    assert output["required"] is False


def test_schema_export_should_match_live_click_tree(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli, ["schema", "export"], prog_name="sccfm-cli")
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    schema_tree = {tuple(command["path"]): command for command in payload["command_tree"]}
    schema_leaf = {tuple(command["path"]): command for command in payload["commands"]}
    click_tree = list(_walk_click_commands(cli))
    click_leaf = {
        path: command for path, command in click_tree if not isinstance(command, click.Group)
    }

    assert set(schema_tree) == {path for path, _command in click_tree}
    assert set(schema_leaf) == set(click_leaf)

    for path, click_command in click_leaf.items():
        schema_options = {option["name"]: option for option in schema_leaf[path]["options"]}
        click_options = [
            parameter for parameter in click_command.params if isinstance(parameter, click.Option)
        ]

        assert set(schema_options) == {option.name for option in click_options}
        for option in click_options:
            assert schema_options[option.name]["aliases"] == [*option.opts, *option.secondary_opts]
            assert schema_options[option.name]["required"] == bool(option.required)
            assert schema_options[option.name]["multiple"] == bool(option.multiple)


def test_schema_examples_should_reference_declared_options(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli, ["schema", "export"], prog_name="sccfm-cli")
    assert result.exit_code == 0, result.output

    for command in json.loads(result.output)["commands"]:
        declared_aliases = {
            alias for option in command["options"] for alias in option["aliases"]
        } | {"--help"}
        command_prefix_len = 1 + len(command["path"])

        for example in command["examples"]:
            tokens = shlex.split(example)
            assert tokens[:command_prefix_len] == ["sccfm-cli", *command["path"]]
            example_flags = [
                token for token in tokens[command_prefix_len:] if token.startswith("-")
            ]
            assert set(example_flags) <= declared_aliases


def test_schema_examples_should_omit_sensitive_argv_options(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli, ["schema", "export"], prog_name="sccfm-cli")
    assert result.exit_code == 0, result.output

    for command in json.loads(result.output)["commands"]:
        sensitive_aliases = {
            alias
            for option in command["options"]
            if option["sensitive"]
            for alias in option["aliases"]
        }
        for example in command["examples"]:
            assert sensitive_aliases.isdisjoint(shlex.split(example))


def _commands_by_name(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {command["command"]: command for command in payload["commands"]}


def _project_version() -> str:
    pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data["project"]
    assert isinstance(project, dict)
    version = project["version"]
    assert isinstance(version, str)
    return version


def _option(options: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next(option for option in options if option["name"] == name)


def _field(fields: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next(field for field in fields if field["name"] == name)


def _constraint(constraints: list[dict[str, Any]], constraint_type: str) -> dict[str, Any]:
    return next(constraint for constraint in constraints if constraint["type"] == constraint_type)


def _constraint_for_options(
    constraints: list[dict[str, Any]],
    constraint_type: str,
    options: list[str],
) -> dict[str, Any]:
    return next(
        constraint
        for constraint in constraints
        if constraint["type"] == constraint_type and constraint.get("options") == options
    )


def _option_group(option_groups: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next(option_group for option_group in option_groups if option_group["name"] == name)


def _walk_click_commands(
    command: click.Command, path: tuple[str, ...] = ()
) -> list[tuple[tuple[str, ...], click.Command]]:
    paths: list[tuple[tuple[str, ...], click.Command]] = []
    if path:
        paths.append((path, command))
    if isinstance(command, click.Group):
        for name, child in sorted(command.commands.items()):
            paths.extend(_walk_click_commands(child, (*path, name)))
    return paths

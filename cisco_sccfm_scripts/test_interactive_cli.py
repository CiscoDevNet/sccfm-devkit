# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from pytest import MonkeyPatch

from cisco_sccfm_cli.models import Config
from cisco_sccfm_cli.services import ConfigService
from cisco_sccfm_scripts import interactive_cli
from cisco_sccfm_scripts.cli_commands import CliCommand, CliParam, build_cli_tree


def test_interactive_task_list_preserves_workflows_under_new_command() -> None:
    task_names = [name for name, _, _ in interactive_cli._TASKS]

    assert task_names == [
        "configure-profile",
        "manage-profiles",
        "import-legacy-vault",
        "run-cli",
        "run-ansible",
        "build-collection",
        "generate-ansible-docs",
        "generate-cli-docs",
        "generate-cli-man-docs",
        "install-cli-man-docs",
        "setup-env",
        "test",
        "run-e2e",
        "lint",
        "format",
    ]


def test_update_profile_uses_canonical_config_service(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.json"
    service = ConfigService(config_path)
    original = Config(profile="lab", region="us", api_token="old-token")
    service.save(original)

    monkeypatch.setattr(interactive_cli, "_select_profile", lambda _: original)
    monkeypatch.setattr(
        "cisco_sccfm_cli.services.ConfigService",
        lambda: service,
    )
    region_prompt = MagicMock()
    region_prompt.unsafe_ask.return_value = "eu"
    token_prompt = MagicMock()
    token_prompt.unsafe_ask.return_value = "new-token"
    monkeypatch.setattr(interactive_cli.questionary, "select", lambda *a, **k: region_prompt)
    monkeypatch.setattr(interactive_cli.questionary, "password", lambda *a, **k: token_prompt)

    interactive_cli._update_profile()

    assert service.load("lab") == Config(profile="lab", region="eu", api_token="new-token")


def test_remove_profile_uses_canonical_config_service(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.json"
    service = ConfigService(config_path)
    existing = Config(profile="lab", region="us", api_token="token")
    service.save(existing)

    monkeypatch.setattr(interactive_cli, "_select_profile", lambda _: existing)
    monkeypatch.setattr("cisco_sccfm_cli.services.ConfigService", lambda: service)
    confirmation = MagicMock()
    confirmation.unsafe_ask.return_value = True
    monkeypatch.setattr(interactive_cli.questionary, "confirm", lambda *a, **k: confirmation)

    interactive_cli._remove_profile()

    assert service.load("lab") is None


def test_configure_command_exposes_hidden_input_for_api_token() -> None:
    tree = build_cli_tree()
    configure = next(node for node in tree if node.name == "configure")
    assert isinstance(configure, CliCommand)

    api_token = next(param for param in configure.params if param.flag == "--api-token")

    assert api_token.hide_input is True


def test_execute_cli_command_masks_secrets_and_uses_password_prompt(
    monkeypatch: MonkeyPatch,
) -> None:
    command = CliCommand(
        name="configure",
        description="Configure a profile",
        args=["configure"],
        params=[
            CliParam(label="Region", flag="--region", required=True),
            CliParam(label="API token", flag="--api-token", required=True, hide_input=True),
        ],
    )
    prompt = MagicMock()
    prompt.unsafe_ask.side_effect = ["us", "super-secret"]
    password_prompt = MagicMock(return_value=prompt)
    monkeypatch.setattr(interactive_cli.questionary, "text", MagicMock(return_value=prompt))
    monkeypatch.setattr(interactive_cli.questionary, "password", password_prompt)
    printed: list[str] = []
    monkeypatch.setattr(interactive_cli.console, "print", lambda message: printed.append(message))
    call = MagicMock(return_value=0)
    monkeypatch.setattr(interactive_cli.subprocess, "call", call)
    cli_main = MagicMock()
    monkeypatch.setattr("cisco_sccfm_cli.cli.cli.main", cli_main)

    interactive_cli._execute_cli_command(command)

    password_prompt.assert_called_once()
    call.assert_not_called()
    cli_main.assert_called_once_with(
        args=["configure", "--region", "us", "--api-token", "super-secret"],
        prog_name="sccfm-cli",
        standalone_mode=False,
    )
    rendered = " ".join(printed)
    assert "super-secret" not in rendered
    assert "--api-token '***'" in rendered


def test_execute_cli_command_without_secrets_uses_subprocess(
    monkeypatch: MonkeyPatch,
) -> None:
    command = CliCommand(
        name="status",
        description="Show status",
        args=["status"],
        params=[],
    )
    call = MagicMock(return_value=0)
    monkeypatch.setattr(interactive_cli.subprocess, "call", call)

    interactive_cli._execute_cli_command(command)

    call.assert_called_once_with(["sccfm-cli", "status"], cwd=interactive_cli._project_root())


def test_run_ansible_examples_omits_vault_argument_when_not_required(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    examples = tmp_path / "sccfm-ansible" / "examples"
    examples.mkdir(parents=True)
    (examples / "show_devices.yml").write_text("- hosts: all\n", encoding="utf-8")
    monkeypatch.setattr(interactive_cli, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(interactive_cli, "_ask", lambda *a, **k: "show_devices.yml")
    call = MagicMock(return_value=0)
    monkeypatch.setattr(interactive_cli.subprocess, "call", call)

    interactive_cli._run_ansible_examples()

    assert call.call_args.args[0] == [
        "ansible-playbook",
        "show_devices.yml",
        "-i",
        "inventory.sccfm.yml",
    ]


def test_run_ansible_examples_adds_vault_argument_when_required(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    examples = tmp_path / "sccfm-ansible" / "examples"
    examples.mkdir(parents=True)
    (examples / "onboard_asas.yml").write_text(
        '- hosts: all\n  vars:\n    password: "{{ vault_asa_password }}"\n',
        encoding="utf-8",
    )
    (examples / ".vault_pass").write_text("secret\n", encoding="utf-8")
    monkeypatch.setattr(interactive_cli, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(interactive_cli, "_ask", lambda *a, **k: "onboard_asas.yml")
    call = MagicMock(return_value=0)
    monkeypatch.setattr(interactive_cli.subprocess, "call", call)

    interactive_cli._run_ansible_examples()

    assert call.call_args.args[0] == [
        "ansible-playbook",
        "onboard_asas.yml",
        "-i",
        "inventory.sccfm.yml",
        "--vault-password-file",
        ".vault_pass",
    ]

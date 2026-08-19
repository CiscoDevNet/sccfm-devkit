# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from pytest import MonkeyPatch

from cisco_sccfm_cli.interactive import customer_tasks
from cisco_sccfm_scripts import interactive_cli


def test_interactive_task_list_preserves_workflows_under_new_command() -> None:
    task_names = [name for name, _, _ in interactive_cli._TASKS]

    assert task_names == [
        "configure-profile",
        "manage-profiles",
        "run-cli",
        "import-legacy-vault",
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

    public_task_names = [task.name for task in customer_tasks()]
    assert task_names[: len(public_task_names)] == public_task_names


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

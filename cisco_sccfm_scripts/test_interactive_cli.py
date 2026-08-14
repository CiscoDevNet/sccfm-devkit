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

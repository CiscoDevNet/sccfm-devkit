# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

import cisco_sccfm_scripts.setup_tokens as setup_tokens
from cisco_sccfm_scripts.setup_tokens import (
    _ensure_vault_pass_headless,
    _resolve_examples_path,
    _update_vars_region,
    _write_env_file,
    main,
)
from cisco_sccfm_scripts.token_store import SavedToken, VaultTokenStore


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _create_examples_layout(root: Path) -> Path:
    examples = root / "sccfm-ansible" / "examples"
    (examples / "group_vars").mkdir(parents=True)
    (examples / ".vault_pass.example").write_text("placeholder\n")
    return examples


def test_default_path_resolves_collection_examples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    examples = _create_examples_layout(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert _resolve_examples_path(None) == examples.resolve()


def test_current_examples_directory_is_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    examples = _create_examples_layout(tmp_path)
    monkeypatch.chdir(examples)

    assert _resolve_examples_path(None) == examples.resolve()


def test_explicit_examples_path_is_supported(tmp_path: Path) -> None:
    examples = tmp_path / "examples"
    examples.mkdir()

    assert _resolve_examples_path(examples) == examples.resolve()


def test_missing_default_path_has_actionable_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(click.ClickException, match="Run from the project root"):
        _resolve_examples_path(None)


def test_generated_files_use_private_modes(tmp_path: Path) -> None:
    root = tmp_path / "project"
    workspace = root / "sccfm-ansible" / "examples"
    workspace.mkdir(parents=True, mode=0o755)
    root_mode = _mode(root)
    workspace_mode = _mode(workspace)

    env_path = _write_env_file(root, "us", "synthetic-token")
    vault_pass = _ensure_vault_pass_headless(workspace, "synthetic-password")
    _update_vars_region(workspace, "us")
    vars_path = workspace / "group_vars" / "all" / "vars.yml"

    assert _mode(root) == root_mode
    assert _mode(workspace) == workspace_mode
    assert _mode(workspace / "group_vars") == 0o700
    assert _mode(workspace / "group_vars" / "all") == 0o700
    assert _mode(env_path) == 0o600
    assert _mode(vault_pass) == 0o600
    assert _mode(vars_path) == 0o600


def test_headless_cli_keeps_path_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_headless(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(setup_tokens, "_run_headless", fake_run_headless)
    result = CliRunner().invoke(
        main,
        ["--region", "us", "--api-token", "synthetic-token"],
    )

    assert result.exit_code == 0, result.output
    assert captured["path"] is None


def test_headless_cli_forwards_typed_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    captured: dict[str, object] = {}

    def fake_run_headless(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("cisco_sccfm_scripts.setup_tokens._run_headless", fake_run_headless)
    result = CliRunner().invoke(
        main,
        [
            "--region",
            "us",
            "--api-token",
            "synthetic-token",
            "--path",
            str(workspace),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["path"] == workspace.resolve()


def test_headless_setup_routes_env_to_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    examples = _create_examples_layout(root)
    monkeypatch.chdir(root)
    captured: dict[str, Path] = {}

    class FakeStore:
        def __init__(self, path: Path) -> None:
            captured["store"] = path

        def list_tokens(self) -> list[SavedToken]:
            return []

        def save_active_and_tokens(self, active: SavedToken, tokens: list[SavedToken]) -> Path:
            return examples / "group_vars" / "all" / "vault.yml"

    def fake_write_env(path: Path, region: str, api_token: str) -> Path:
        captured["env"] = path
        return path / ".env"

    monkeypatch.setattr(setup_tokens, "_project_root", lambda: root)
    monkeypatch.setattr(setup_tokens, "_verify_ansible_vault", lambda: None)
    monkeypatch.setattr(
        setup_tokens,
        "_ensure_vault_pass_headless",
        lambda path, password: path / ".vault_pass",
    )
    monkeypatch.setattr(setup_tokens, "VaultTokenStore", FakeStore)
    monkeypatch.setattr(setup_tokens, "_write_env_file", fake_write_env)
    monkeypatch.setattr(setup_tokens, "_update_vars_region", lambda path, region: None)
    monkeypatch.setattr(setup_tokens, "_update_cli_config", lambda *args, **kwargs: None)

    setup_tokens._run_headless(
        region="us",
        api_token="synthetic-token",
        name="default",
        profile="default",
        vault_password="synthetic-password",
        path=None,
    )

    assert captured == {"store": examples.resolve(), "env": root}


def test_vault_store_encrypts_atomically_with_private_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    store = VaultTokenStore(workspace)
    token = SavedToken(name="test", region="us", token="synthetic-token")

    vault_path = store.save_active_and_tokens(token, [token])

    assert _mode(vault_path) == 0o600
    assert vault_path.read_bytes().startswith(b"$ANSIBLE_VAULT;")
    assert store.list_tokens() == [token]
    assert list(vault_path.parent.glob(".vault.*.tmp")) == []


def test_vault_store_removes_plaintext_temporary_file_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    vault_path = workspace / "group_vars" / "all" / "vault.yml"
    vault_path.parent.mkdir(parents=True)
    original = b"$ANSIBLE_VAULT;1.1;AES256\nexisting-ciphertext\n"
    vault_path.write_bytes(original)
    store = VaultTokenStore(workspace)
    token = SavedToken(name="test", region="us", token="synthetic-token")

    def failed_encrypt(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="failed")

    monkeypatch.setattr("cisco_sccfm_scripts.token_store.subprocess.run", failed_encrypt)
    with pytest.raises(RuntimeError, match="ansible-vault encrypt failed"):
        store.save_active_and_tokens(token, [token])

    assert vault_path.read_bytes() == original
    assert list(vault_path.parent.glob(".vault.*.tmp")) == []


def test_vault_store_rejects_success_without_ciphertext(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    vault_path = workspace / "group_vars" / "all" / "vault.yml"
    vault_path.parent.mkdir(parents=True)
    original = b"$ANSIBLE_VAULT;1.1;AES256\nexisting-ciphertext\n"
    vault_path.write_bytes(original)
    store = VaultTokenStore(workspace)
    token = SavedToken(name="test", region="us", token="synthetic-token")

    def false_success(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr("cisco_sccfm_scripts.token_store.subprocess.run", false_success)
    with pytest.raises(RuntimeError, match="valid encrypted output"):
        store.save_active_and_tokens(token, [token])

    assert vault_path.read_bytes() == original
    assert list(vault_path.parent.glob(".vault.*.tmp")) == []


def test_vault_store_failure_without_previous_vault_leaves_no_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    store = VaultTokenStore(workspace)
    token = SavedToken(name="test", region="us", token="synthetic-token")

    def failed_encrypt(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="failed")

    monkeypatch.setattr("cisco_sccfm_scripts.token_store.subprocess.run", failed_encrypt)
    with pytest.raises(RuntimeError, match="ansible-vault encrypt failed"):
        store.save_active_and_tokens(token, [token])

    vault_path = workspace / "group_vars" / "all" / "vault.yml"
    assert not vault_path.exists()
    assert list(vault_path.parent.glob(".vault.*.tmp")) == []


def test_vault_store_uses_separate_private_temporary_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    store = VaultTokenStore(workspace)
    token = SavedToken(name="test", region="us", token="synthetic-token")
    captured: dict[str, Path] = {}

    def inspect_encrypt(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        plaintext_path = Path(command[2])
        ciphertext_path = Path(command[command.index("--output") + 1])
        assert plaintext_path != ciphertext_path
        assert _mode(plaintext_path) == 0o600
        assert _mode(ciphertext_path) == 0o600
        ciphertext_path.write_bytes(b"$ANSIBLE_VAULT;1.1;AES256\nsynthetic-ciphertext\n")
        captured.update(plaintext=plaintext_path, ciphertext=ciphertext_path)
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("cisco_sccfm_scripts.token_store.subprocess.run", inspect_encrypt)
    vault_path = store.save_active_and_tokens(token, [token])

    assert vault_path.read_bytes().startswith(b"$ANSIBLE_VAULT;")
    assert not captured["plaintext"].exists()
    assert not captured["ciphertext"].exists()


def test_vault_store_cleans_temporary_files_when_encryption_is_interrupted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    store = VaultTokenStore(workspace)
    token = SavedToken(name="test", region="us", token="synthetic-token")

    def interrupted_encrypt(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise KeyboardInterrupt

    monkeypatch.setattr("cisco_sccfm_scripts.token_store.subprocess.run", interrupted_encrypt)
    with pytest.raises(KeyboardInterrupt):
        store.save_active_and_tokens(token, [token])

    vault_path = workspace / "group_vars" / "all" / "vault.yml"
    assert not vault_path.exists()
    assert list(vault_path.parent.glob(".vault.*.tmp")) == []

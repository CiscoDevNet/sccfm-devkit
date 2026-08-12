# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import traceback
from pathlib import Path
from typing import cast

import click
import pytest
import yaml
from click.testing import CliRunner

import cisco_sccfm_scripts.devkit_cli as devkit_cli
import cisco_sccfm_scripts.setup_tokens as setup_tokens
from cisco_sccfm_cli.models import Config
from cisco_sccfm_cli.services import ConfigService
from cisco_sccfm_scripts.setup_tokens import (
    _ensure_vault_pass_headless,
    _resolve_examples_path,
    _update_vars_region,
    _write_env_file,
    main,
)
from cisco_sccfm_scripts.token_store import SavedToken, VaultTokenStore


@pytest.fixture(autouse=True)
def _isolate_cli_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every token-workspace test away from the developer's real CLI config."""
    monkeypatch.setenv("SCCFM_CONFIG", str(tmp_path / "isolated-cli" / "config.json"))


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _create_examples_layout(root: Path) -> Path:
    examples = root / "sccfm-ansible" / "examples"
    (examples / "group_vars").mkdir(parents=True)
    (examples / ".vault_pass.example").write_text("placeholder\n")
    return examples


def _view_vault(workspace: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            "ansible-vault",
            "view",
            str(workspace / "group_vars" / "all" / "vault.yml"),
            "--vault-password-file",
            str(workspace / ".vault_pass"),
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    return cast(dict[str, object], yaml.safe_load(result.stdout))


def _write_encrypted_vault(workspace: Path, payload: object) -> Path:
    plaintext_path = workspace / "vault-plaintext.yml"
    plaintext_path.write_text(
        "---\n" + yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )
    vault_path = workspace / "group_vars" / "all" / "vault.yml"
    vault_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ansible-vault",
            "encrypt",
            str(plaintext_path),
            "--output",
            str(vault_path),
            "--vault-password-file",
            str(workspace / ".vault_pass"),
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    plaintext_path.unlink()
    return vault_path


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
    assert _mode(workspace / "group_vars") == 0o755
    assert _mode(workspace / "group_vars" / "all") == 0o755
    assert _mode(env_path) == 0o600
    assert _mode(vault_pass) == 0o600
    assert _mode(vars_path) == 0o644


@pytest.mark.parametrize(
    "path",
    [
        "..env.synthetic-crash-leftover",
        "sccfm-ansible/examples/group_vars/all/.vault.plaintext.synthetic.tmp",
    ],
)
def test_plaintext_crash_leftovers_are_gitignored(path: str) -> None:
    repository = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", path],
        cwd=repository,
        check=False,
    )

    assert result.returncode == 0


def test_env_file_shell_quotes_token_without_executing_content(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    marker = tmp_path / "must-not-exist"
    token = f'synthetic-token"; touch {marker}; printf "$(id)`id`\\value'

    env_path = _write_env_file(root, "us", token)
    result = subprocess.run(
        [
            "/bin/sh",
            "-c",
            '. "$1"; printf "%s\\n%s\\n" "$SCCFM_REGION" "$SCCFM_API_TOKEN"',
            "sh",
            str(env_path),
        ],
        capture_output=True,
        check=True,
        text=True,
    )

    assert result.stdout.splitlines() == ["us", token]
    assert not marker.exists()


def test_env_file_replaces_exported_and_plain_assignments_without_retaining_old_secret(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    old_secret = "sec-old-token-must-disappear"
    env_path = root / ".env"
    env_path.write_text(
        f"SCCFM_API_TOKEN={old_secret}\n  export SCCFM_API_TOKEN={old_secret}\n"
        "SCCFM_REGION=int\n",
        encoding="utf-8",
    )

    _write_env_file(root, "eu", "new-token")

    content = env_path.read_text(encoding="utf-8")
    assert old_secret not in content
    assert content.count("SCCFM_API_TOKEN=") == 1
    assert content.count("SCCFM_REGION=") == 1


@pytest.mark.parametrize("kind", ["directory", "fifo"])
def test_existing_vault_password_path_must_be_regular(
    tmp_path: Path,
    kind: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    vault_pass = workspace / ".vault_pass"
    if kind == "directory":
        vault_pass.mkdir(mode=0o700)
    else:
        vault_pass.parent.mkdir(parents=True, exist_ok=True)
        vault_pass_path = str(vault_pass)
        os.mkfifo(vault_pass_path, mode=0o600)
    original_mode = _mode(vault_pass)

    with pytest.raises(click.ClickException, match="not a regular file"):
        _ensure_vault_pass_headless(workspace, "synthetic-password")

    assert _mode(vault_pass) == original_mode


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
    assert "process listings and shell history" in result.stderr
    if "synthetic-token" in result.output:
        pytest.fail("Sensitive value was exposed by change-tokens.", pytrace=False)


def test_headless_cli_reads_api_token_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "sec005-environment-sentinel-9f31"
    captured: dict[str, object] = {}

    def fake_run_headless(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(setup_tokens, "_run_headless", fake_run_headless)
    result = CliRunner().invoke(
        main,
        ["--region", "us"],
        env={"SCCFM_API_TOKEN": token},
    )

    assert result.exit_code == 0, result.output
    assert captured["api_token"] == token
    assert "process listings and shell history" not in result.output
    observed = f"{result.stdout}\n{result.stderr}\n{result.exception!r}"
    if token in observed:
        pytest.fail("Sensitive value was exposed by change-tokens.", pytrace=False)


def test_headless_cli_reads_vault_password_from_environment_without_exposure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_token = "sec005-environment-api-sentinel-115b"
    vault_password = "sec009-environment-vault-sentinel-6c92"
    captured: dict[str, object] = {}

    def fake_run_headless(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(setup_tokens, "_run_headless", fake_run_headless)
    result = CliRunner().invoke(
        main,
        ["--region", "us"],
        env={
            "SCCFM_API_TOKEN": api_token,
            "SCCFM_VAULT_PASSWORD": vault_password,
        },
    )

    assert result.exit_code == 0, result.output
    assert captured["vault_password"] == vault_password
    assert "passing --vault-password directly" not in result.stderr
    observed = f"{result.stdout}\n{result.stderr}\n{result.exception!r}"
    for secret in (api_token, vault_password):
        if secret in observed:
            pytest.fail("Sensitive value was exposed by change-tokens.", pytrace=False)


def test_headless_cli_warns_for_legacy_vault_password_option_without_exposure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_token = "sec005-environment-api-sentinel-1d38"
    vault_password = "sec009-command-vault-sentinel-80f4"
    captured: dict[str, object] = {}

    def fake_run_headless(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(setup_tokens, "_run_headless", fake_run_headless)
    result = CliRunner().invoke(
        main,
        ["--region", "us", "--vault-password", vault_password],
        env={"SCCFM_API_TOKEN": api_token},
    )

    assert result.exit_code == 0, result.output
    assert captured["vault_password"] == vault_password
    assert "passing --vault-password directly" in result.stderr
    assert "SCCFM_VAULT_PASSWORD" in result.stderr
    assert ".vault_pass" in result.stderr
    observed = f"{result.stdout}\n{result.stderr}\n{result.exception!r}"
    for secret in (api_token, vault_password):
        if secret in observed:
            pytest.fail("Sensitive value was exposed by change-tokens.", pytrace=False)


def test_interactive_api_token_prompt_hides_input(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_prompt(prompt: str, **kwargs: object) -> str:
        captured.update(prompt=prompt, **kwargs)
        return "synthetic-token"

    monkeypatch.setattr(setup_tokens.click, "prompt", fake_prompt)

    assert setup_tokens._prompt_token() == "synthetic-token"
    assert captured["hide_input"] is True


def test_change_tokens_help_recommends_environment_input() -> None:
    result = CliRunner().invoke(main, ["--help"])
    help_text = " ".join(result.output.split())

    assert result.exit_code == 0, result.output
    assert "SCCFM_API_TOKEN" in help_text
    assert "SCCFM_VAULT_PASSWORD" in help_text
    assert "existing private .vault_pass" in help_text
    assert "process listings and shell history" in help_text


def test_missing_vault_password_recommends_private_inputs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(click.ClickException) as exc_info:
        _ensure_vault_pass_headless(workspace, None)

    message = str(exc_info.value)
    assert "SCCFM_VAULT_PASSWORD" in message
    assert "private .vault_pass" in message


def test_whitespace_vault_password_is_rejected_without_creating_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(click.ClickException, match="No vault password found"):
        _ensure_vault_pass_headless(workspace, " \t ")

    assert not (workspace / ".vault_pass").exists()


def test_interactive_token_name_retries_blank_and_reserved_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(["  ", "_new", "vault-active", " production "])
    rendered: list[str] = []
    monkeypatch.setattr(
        setup_tokens.click,
        "prompt",
        lambda *args, **kwargs: next(answers),
    )
    monkeypatch.setattr(
        setup_tokens.console,
        "print",
        lambda value="", *args, **kwargs: rendered.append(str(value)),
    )

    assert setup_tokens._prompt_token_name() == "production"
    assert sum("token name" in line for line in rendered) == 3


@pytest.mark.parametrize("name", ["", "  ", "_new", "back", "vault-active", "legacy-active-2"])
def test_user_token_names_reject_invalid_and_internal_values(name: str) -> None:
    with pytest.raises(click.ClickException, match="token name"):
        setup_tokens._saved_token(name=name, region="us", token="synthetic-token")


def test_saved_token_representation_omits_token_value() -> None:
    token = "sec005-repr-sentinel-284c"

    rendered = repr(SavedToken(name="default", region="us", token=token))

    if token in rendered:
        pytest.fail("Sensitive value was exposed by SavedToken repr.", pytrace=False)
    assert "name='default'" in rendered
    assert "region='us'" in rendered


def test_credential_snapshot_representation_omits_file_content(tmp_path: Path) -> None:
    sentinel = b"sec-snapshot-content-sentinel"
    snapshot = setup_tokens._FileSnapshot(
        path=tmp_path / "credential",
        content=sentinel,
        mode=0o600,
    )

    assert sentinel.decode() not in repr(snapshot)


@pytest.mark.skipif(os.name != "posix", reason="descriptor-relative rollback is POSIX-only")
def test_credential_transaction_rolls_back_through_pinned_parent_after_ancestor_swap(
    tmp_path: Path,
) -> None:
    trusted_parent = tmp_path / "trusted" / "credentials"
    trusted_parent.mkdir(parents=True)
    credential_path = trusted_parent / "token"
    original = b"trusted-original"
    credential_path.write_bytes(original)
    credential_path.chmod(0o640)

    attacker_parent = tmp_path / "attacker" / "credentials"
    attacker_parent.mkdir(parents=True)
    attacker_path = attacker_parent / "token"
    attacker = b"attacker-owned"
    attacker_path.write_bytes(attacker)
    moved_parent = tmp_path / "moved-trusted"

    with pytest.raises(RuntimeError, match="trigger rollback"):
        with setup_tokens._credential_transaction([credential_path]):
            credential_path.write_bytes(b"partially-updated")
            trusted_parent.rename(moved_parent)
            trusted_parent.symlink_to(attacker_parent, target_is_directory=True)
            raise RuntimeError("trigger rollback")

    assert (moved_parent / "token").read_bytes() == original
    assert _mode(moved_parent / "token") == 0o640
    assert attacker_path.read_bytes() == attacker


@pytest.mark.skipif(os.name != "posix", reason="descriptor-relative rollback is POSIX-only")
def test_credential_transaction_removes_new_file_from_pinned_parent_after_ancestor_swap(
    tmp_path: Path,
) -> None:
    trusted_parent = tmp_path / "trusted" / "credentials"
    trusted_parent.mkdir(parents=True)
    credential_path = trusted_parent / "token"
    attacker_parent = tmp_path / "attacker" / "credentials"
    attacker_parent.mkdir(parents=True)
    attacker_path = attacker_parent / "token"
    attacker = b"attacker-owned"
    attacker_path.write_bytes(attacker)
    moved_parent = tmp_path / "moved-trusted"

    with pytest.raises(RuntimeError, match="trigger rollback"):
        with setup_tokens._credential_transaction([credential_path]):
            credential_path.write_bytes(b"new-credential")
            trusted_parent.rename(moved_parent)
            trusted_parent.symlink_to(attacker_parent, target_is_directory=True)
            raise RuntimeError("trigger rollback")

    assert not (moved_parent / "token").exists()
    assert attacker_path.read_bytes() == attacker


def test_credential_transaction_supports_missing_parent_directories(tmp_path: Path) -> None:
    credential_path = tmp_path / "new" / "nested" / "token"

    with setup_tokens._credential_transaction([credential_path]):
        credential_path.write_bytes(b"created")

    assert credential_path.read_bytes() == b"created"


@pytest.mark.skipif(os.name != "posix", reason="descriptor-relative writes are POSIX-only")
def test_credential_transaction_successful_write_stays_with_pinned_parent_after_swap(
    tmp_path: Path,
) -> None:
    trusted_parent = tmp_path / "trusted" / "credentials"
    trusted_parent.mkdir(parents=True)
    credential_path = trusted_parent / "token"
    credential_path.write_bytes(b"trusted-original")
    attacker_parent = tmp_path / "attacker" / "credentials"
    attacker_parent.mkdir(parents=True)
    attacker_path = attacker_parent / "token"
    attacker = b"attacker-owned"
    attacker_path.write_bytes(attacker)
    moved_parent = tmp_path / "moved-trusted"

    with setup_tokens._credential_transaction([credential_path]):
        trusted_parent.rename(moved_parent)
        trusted_parent.symlink_to(attacker_parent, target_is_directory=True)
        setup_tokens._write_bytes(credential_path, b"trusted-update", mode=0o600)

    assert (moved_parent / "token").read_bytes() == b"trusted-update"
    assert attacker_path.read_bytes() == attacker


@pytest.mark.skipif(os.name != "posix", reason="descriptor-relative writes are POSIX-only")
def test_credential_transaction_normalizes_platform_temp_aliases() -> None:
    alias_path = Path(tempfile.mkdtemp()) / "missing" / "credential"

    with setup_tokens._credential_transaction([alias_path]):
        setup_tokens._write_bytes(alias_path, b"created", mode=0o600)

    assert alias_path.read_bytes() == b"created"


@pytest.mark.skipif(os.name != "posix", reason="descriptor path checks are POSIX-only")
def test_credential_transaction_rejects_preexisting_symlink_ancestor(tmp_path: Path) -> None:
    attacker_parent = tmp_path / "attacker"
    attacker_parent.mkdir()
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(attacker_parent, target_is_directory=True)

    with pytest.raises(click.ClickException, match="symbolic link"):
        with setup_tokens._credential_transaction([linked_parent / "token"]):
            pytest.fail("transaction body must not run", pytrace=False)

    assert not (attacker_parent / "token").exists()


def test_platform_path_normalization_does_not_require_uname(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(setup_tokens.sys, "platform", "win32")

    assert (
        setup_tokens._platform_normalized_path(tmp_path / "token")
        == (tmp_path / "token").absolute()
    )


def test_transaction_absent_vault_does_not_fall_back_to_injected_path(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    vault_path = workspace / "group_vars" / "all" / "vault.yml"
    attacker_parent = tmp_path / "attacker-all"
    attacker_parent.mkdir()
    (attacker_parent / "vault.yml").write_text("attacker-injected", encoding="utf-8")
    moved_parent = tmp_path / "moved-all"

    with setup_tokens._credential_transaction([vault_path, workspace / ".vault_pass"]):
        vault_path.parent.rename(moved_parent)
        vault_path.parent.symlink_to(attacker_parent, target_is_directory=True)
        assert VaultTokenStore(workspace)._decrypt_vault() is None

    assert (attacker_parent / "vault.yml").read_text(encoding="utf-8") == "attacker-injected"


def test_transaction_vault_encrypt_uses_staged_password_for_both_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    store = VaultTokenStore(workspace)
    token = SavedToken(name="test", region="us", token="synthetic-token")
    password_arguments: list[Path] = []
    real_run = subprocess.run

    def capture_password(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        password_arguments.append(Path(command[command.index("--vault-password-file") + 1]))
        return cast(subprocess.CompletedProcess[str], real_run(command, **kwargs))

    monkeypatch.setattr("cisco_sccfm_scripts.token_store.subprocess.run", capture_password)
    paths = [store._vault_path, workspace / ".vault_pass"]
    with setup_tokens._credential_transaction(paths):
        store.save_active_and_tokens(token, [token])

    assert len(password_arguments) == 2
    assert password_arguments[0] == password_arguments[1]
    assert password_arguments[0] != workspace / ".vault_pass"
    assert not password_arguments[0].exists()


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
        def __init__(self, path: Path, migration_region: str | None = None) -> None:
            captured["store"] = path
            assert migration_region is None

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
        legacy_region=None,
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
    assert _view_vault(workspace) == {
        "vault_sccfm_api_token": "synthetic-token",
        "sccfm_saved_tokens": [{"name": "test", "region": "us", "token": "synthetic-token"}],
    }
    assert store.list_tokens() == [token]
    assert list(vault_path.parent.glob(".vault.*.tmp")) == []


def test_headless_setup_rolls_back_every_credential_surface_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    workspace = root / "sccfm-ansible" / "examples"
    workspace.mkdir(parents=True)
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    config_path = tmp_path / "cli" / "config.json"
    monkeypatch.setenv("SCCFM_CONFIG", str(config_path))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    old = SavedToken(name="old", region="eu", token="old-token")
    VaultTokenStore(workspace).save_active_and_tokens(old, [old])
    _write_env_file(root, "eu", "old-token")
    _update_vars_region(workspace, "eu")
    ConfigService(config_path).save(Config(profile="staging", region="eu", api_token="old-token"))
    paths = setup_tokens._credential_state_paths(root, workspace)
    before = {path: path.read_bytes() for path in paths}
    monkeypatch.setattr(setup_tokens, "_project_root", lambda: root)
    monkeypatch.setattr(setup_tokens, "_verify_ansible_vault", lambda: None)
    monkeypatch.setattr(
        setup_tokens,
        "_update_cli_config",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("injected config failure")),
    )

    with pytest.raises(OSError, match="injected config failure"):
        setup_tokens._run_headless(
            region="us",
            api_token="new-token",
            name="new",
            profile="staging",
            vault_password=None,
            legacy_region=None,
            path=workspace,
        )

    assert {path: path.read_bytes() for path in paths} == before


def test_pristine_vault_store_lists_no_tokens_without_password_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    assert VaultTokenStore(workspace).list_tokens() == []


def test_new_vault_rejects_world_readable_password_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    password_path = _ensure_vault_pass_headless(workspace, "synthetic-password")
    password_path.chmod(0o644)
    token = SavedToken(name="test", region="us", token="synthetic-token")

    with pytest.raises(RuntimeError, match="mode 0600"):
        VaultTokenStore(workspace).save_active_and_tokens(token, [token])

    assert not (workspace / "group_vars" / "all" / "vault.yml").exists()


def test_saved_token_normalizes_values_and_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    token = SavedToken(name=" production ", region="US", token=" synthetic-token ")

    store = VaultTokenStore(workspace)
    store.save_active_and_tokens(token, [token])

    assert token == SavedToken(name="production", region="us", token="synthetic-token")
    assert store.list_tokens() == [token]


@pytest.mark.parametrize(
    "tokens",
    [
        [
            SavedToken(name="duplicate", region="us", token="first-token"),
            SavedToken(name="duplicate", region="eu", token="second-token"),
        ],
        [
            SavedToken(name="first", region="us", token="duplicate-token"),
            SavedToken(name="second", region="eu", token="duplicate-token"),
        ],
    ],
    ids=["duplicate-name", "duplicate-value"],
)
def test_vault_store_rejects_ambiguous_tokens_without_overwriting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tokens: list[SavedToken],
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    original_token = SavedToken(name="original", region="us", token="original-token")
    store = VaultTokenStore(workspace)
    vault_path = store.save_active_and_tokens(original_token, [original_token])
    original = vault_path.read_bytes()

    with pytest.raises(ValueError, match="unique"):
        store.save_active_and_tokens(tokens[0], tokens)

    assert vault_path.read_bytes() == original


def test_vault_store_migrates_legacy_active_key_and_preserves_saved_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    store = VaultTokenStore(workspace)
    saved_tokens = [
        SavedToken(name="production", region="us", token="synthetic-production-token"),
        SavedToken(name="staging", region="int", token="synthetic-staging-token"),
    ]
    store._encrypt_vault(
        {
            "sccfm_api_token": "synthetic-production-token",
            "sccfm_saved_tokens": [
                {"name": token.name, "region": token.region, "token": token.token}
                for token in saved_tokens
            ],
        }
    )
    assert _view_vault(workspace) == {
        "sccfm_api_token": "synthetic-production-token",
        "sccfm_saved_tokens": [
            {
                "name": "production",
                "region": "us",
                "token": "synthetic-production-token",
            },
            {"name": "staging", "region": "int", "token": "synthetic-staging-token"},
        ],
    }

    loaded_tokens = store.list_tokens()
    assert loaded_tokens == saved_tokens
    store.save_active_and_tokens(loaded_tokens[1], loaded_tokens)

    payload = _view_vault(workspace)
    assert payload == {
        "vault_sccfm_api_token": "synthetic-staging-token",
        "sccfm_saved_tokens": [
            {
                "name": "production",
                "region": "us",
                "token": "synthetic-production-token",
            },
            {"name": "staging", "region": "int", "token": "synthetic-staging-token"},
        ],
    }
    assert "sccfm_api_token" not in payload


def test_existing_reserved_token_name_remains_compatible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    _write_encrypted_vault(
        workspace,
        {
            "vault_sccfm_api_token": "existing-token",
            "sccfm_saved_tokens": [{"name": "back", "region": "us", "token": "existing-token"}],
        },
    )

    assert VaultTokenStore(workspace).list_tokens() == [
        SavedToken(name="back", region="us", token="existing-token")
    ]


@pytest.mark.parametrize("represented_current", [False, True])
def test_vault_store_rejects_ambiguous_distinct_current_and_legacy_tokens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    represented_current: bool,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    saved = (
        [{"name": "current", "region": "us", "token": "current-token"}]
        if represented_current
        else []
    )
    vault_path = _write_encrypted_vault(
        workspace,
        {
            "vault_sccfm_api_token": "current-token",
            "sccfm_api_token": "legacy-token",
            "sccfm_saved_tokens": saved,
        },
    )
    original = vault_path.read_bytes()
    (workspace / "group_vars" / "all" / "vars.yml").write_text(
        "---\nsccfm_region: us\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="migrate them manually"):
        VaultTokenStore(workspace).list_tokens()

    assert vault_path.read_bytes() == original


def test_vault_store_rejects_duplicate_decrypted_keys_without_overwriting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    vault_path = workspace / "group_vars" / "all" / "vault.yml"
    vault_path.parent.mkdir(parents=True)
    original = b"$ANSIBLE_VAULT;1.1;AES256\nsynthetic-ciphertext\n"
    vault_path.write_bytes(original)
    plaintext = (
        "vault_asa_password: first-secret\n"
        "vault_asa_password: second-secret\n"
        "vault_sccfm_api_token: active-token\n"
    )
    monkeypatch.setattr(
        "cisco_sccfm_scripts.token_store.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=plaintext,
            stderr="",
        ),
    )

    with pytest.raises(RuntimeError, match="valid YAML"):
        VaultTokenStore(workspace).list_tokens()

    assert vault_path.read_bytes() == original


def test_vault_store_allows_explicit_override_of_yaml_merge_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    vault_path = workspace / "group_vars" / "all" / "vault.yml"
    vault_path.parent.mkdir(parents=True)
    vault_path.write_bytes(b"$ANSIBLE_VAULT;1.1;AES256\nsynthetic-ciphertext\n")
    plaintext = (
        "shared: &shared\n"
        "  setting: inherited\n"
        "application:\n"
        "  <<: *shared\n"
        "  setting: explicit\n"
        "vault_sccfm_api_token: active-token\n"
        "sccfm_saved_tokens:\n"
        "  - name: active\n"
        "    region: us\n"
        "    token: active-token\n"
    )
    monkeypatch.setattr(
        "cisco_sccfm_scripts.token_store.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=plaintext,
            stderr="",
        ),
    )

    assert VaultTokenStore(workspace).list_tokens() == [
        SavedToken(name="active", region="us", token="active-token")
    ]


def test_active_only_token_rejects_duplicate_region_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    vault_path = _write_encrypted_vault(
        workspace,
        {"vault_sccfm_api_token": "active-token"},
    )
    original = vault_path.read_bytes()
    (workspace / "group_vars" / "all" / "vars.yml").write_text(
        "sccfm_region: eu\nsccfm_region: us\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Cannot read sccfm_region"):
        VaultTokenStore(workspace).list_tokens()

    assert vault_path.read_bytes() == original


def test_dangling_vault_symlink_fails_before_other_headless_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    workspace = root / "sccfm-ansible" / "examples"
    workspace.mkdir(parents=True)
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    vault_path = workspace / "group_vars" / "all" / "vault.yml"
    vault_path.parent.mkdir(parents=True, exist_ok=True)
    vault_path.symlink_to(workspace / "missing-vault")
    monkeypatch.setattr(setup_tokens, "_project_root", lambda: root)
    monkeypatch.setattr(setup_tokens, "_verify_ansible_vault", lambda: None)

    with pytest.raises(RuntimeError, match="symlinked vault"):
        setup_tokens._run_headless(
            region="us",
            api_token="new-token",
            name="new",
            profile="default",
            vault_password=None,
            legacy_region=None,
            path=workspace,
        )

    assert vault_path.is_symlink()
    assert not (root / ".env").exists()
    assert not (workspace / "group_vars" / "all" / "vars.yml").exists()


def test_dangling_vars_symlink_fails_before_other_headless_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    workspace = root / "sccfm-ansible" / "examples"
    workspace.mkdir(parents=True)
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    _write_encrypted_vault(workspace, {"vault_sccfm_api_token": "old-token"})
    vars_path = workspace / "group_vars" / "all" / "vars.yml"
    vars_path.symlink_to(workspace / "missing-vars")
    monkeypatch.setattr(setup_tokens, "_project_root", lambda: root)
    monkeypatch.setattr(setup_tokens, "_verify_ansible_vault", lambda: None)

    with pytest.raises(RuntimeError, match="symlinked vars.yml"):
        setup_tokens._run_headless(
            region="us",
            api_token="new-token",
            name="new",
            profile="default",
            vault_password=None,
            legacy_region="eu",
            path=workspace,
        )

    assert vars_path.is_symlink()
    assert not (root / ".env").exists()


def test_vault_store_preserves_template_device_secrets_and_arbitrary_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    existing_payload = {
        "vault_sccfm_api_token": "old-active-token",
        "sccfm_saved_tokens": [{"name": "old", "region": "eu", "token": "old-active-token"}],
        "vault_asa_branch_office_01_password": "synthetic-branch-password",
        "vault_asa_datacenter_01_password": "synthetic-datacenter-password",
        "nested_application_settings": {"enabled": True, "retries": 3},
        "unrelated_list": ["alpha", "beta"],
    }
    _write_encrypted_vault(workspace, existing_payload)
    store = VaultTokenStore(workspace)
    active = SavedToken(name="new", region="us", token="new-active-token")

    store.save_active_and_tokens(active, [active])

    assert _view_vault(workspace) == {
        **{
            key: value
            for key, value in existing_payload.items()
            if key not in {"vault_sccfm_api_token", "sccfm_saved_tokens"}
        },
        "vault_sccfm_api_token": "new-active-token",
        "sccfm_saved_tokens": [{"name": "new", "region": "us", "token": "new-active-token"}],
    }


def test_vault_store_preserves_active_only_current_token_from_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    _write_encrypted_vault(
        workspace,
        {
            "vault_sccfm_api_token": "template-active-token",
            "vault_asa_branch_office_01_password": "synthetic-device-password",
        },
    )
    monkeypatch.setenv("SCCFM_REGION", "apj")
    (workspace / "group_vars" / "all" / "vars.yml").write_text(
        "---\nsccfm_region: \"{{ lookup('env', 'SCCFM_REGION') }}\"\n",
        encoding="utf-8",
    )
    store = VaultTokenStore(workspace)
    replacement = SavedToken(name="replacement", region="us", token="replacement-token")

    assert store.list_tokens() == [
        SavedToken(name="vault-active", region="apj", token="template-active-token")
    ]
    store.save_active_and_tokens(replacement, [replacement])

    assert _view_vault(workspace) == {
        "vault_sccfm_api_token": "replacement-token",
        "vault_asa_branch_office_01_password": "synthetic-device-password",
        "sccfm_saved_tokens": [
            {"name": "replacement", "region": "us", "token": "replacement-token"},
            {"name": "vault-active", "region": "apj", "token": "template-active-token"},
        ],
    }


def test_headless_setup_uses_separate_legacy_region_for_dynamic_template_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    workspace = root / "sccfm-ansible" / "examples"
    workspace.mkdir(parents=True)
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    monkeypatch.delenv("SCCFM_REGION", raising=False)
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    _write_encrypted_vault(
        workspace,
        {
            "vault_sccfm_api_token": "template-active-token",
            "vault_asa_branch_password": "synthetic-device-password",
        },
    )
    vars_path = workspace / "group_vars" / "all" / "vars.yml"
    vars_path.write_text(
        "---\nsccfm_region: \"{{ lookup('env', 'SCCFM_REGION') }}\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(setup_tokens, "_project_root", lambda: root)
    monkeypatch.setattr(setup_tokens, "_verify_ansible_vault", lambda: None)
    monkeypatch.setattr(setup_tokens, "_update_cli_config", lambda *args, **kwargs: None)

    setup_tokens._run_headless(
        region="us",
        api_token="replacement-token",
        name="replacement",
        profile="default",
        vault_password=None,
        legacy_region="eu",
        path=workspace,
    )

    assert _view_vault(workspace) == {
        "vault_sccfm_api_token": "replacement-token",
        "vault_asa_branch_password": "synthetic-device-password",
        "sccfm_saved_tokens": [
            {"name": "replacement", "region": "us", "token": "replacement-token"},
            {"name": "vault-active", "region": "eu", "token": "template-active-token"},
        ],
    }
    assert "sccfm_region: us" in vars_path.read_text(encoding="utf-8")


def test_headless_setup_does_not_infer_old_token_region_from_new_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    workspace = root / "sccfm-ansible" / "examples"
    workspace.mkdir(parents=True)
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    monkeypatch.delenv("SCCFM_REGION", raising=False)
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    vault_path = _write_encrypted_vault(
        workspace,
        {"vault_sccfm_api_token": "old-eu-token"},
    )
    vars_path = workspace / "group_vars" / "all" / "vars.yml"
    dynamic_vars = "---\nsccfm_region: \"{{ lookup('env', 'SCCFM_REGION') }}\"\n"
    vars_path.write_text(dynamic_vars, encoding="utf-8")
    original = vault_path.read_bytes()
    monkeypatch.setattr(setup_tokens, "_project_root", lambda: root)
    monkeypatch.setattr(setup_tokens, "_verify_ansible_vault", lambda: None)

    with pytest.raises(click.ClickException, match="SCCFM_LEGACY_REGION"):
        setup_tokens._run_headless(
            region="us",
            api_token="new-us-token",
            name="replacement",
            profile="default",
            vault_password=None,
            legacy_region=None,
            path=workspace,
        )

    assert vault_path.read_bytes() == original
    assert vars_path.read_text(encoding="utf-8") == dynamic_vars
    assert not (root / ".env").exists()


def test_explicit_legacy_region_overrides_ambient_region_for_old_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    monkeypatch.setenv("SCCFM_REGION", "us")
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    _write_encrypted_vault(
        workspace,
        {"vault_sccfm_api_token": "old-eu-token"},
    )
    (workspace / "group_vars" / "all" / "vars.yml").write_text(
        "---\nsccfm_region: \"{{ lookup('env', 'SCCFM_REGION') }}\"\n",
        encoding="utf-8",
    )

    assert VaultTokenStore(workspace, migration_region="eu").list_tokens() == [
        SavedToken(name="vault-active", region="eu", token="old-eu-token")
    ]


def test_vault_store_migrates_active_only_legacy_vault_without_stranding_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    _write_encrypted_vault(
        workspace,
        {
            "sccfm_api_token": "legacy-active-token",
            "vault_asa_branch_office_01_password": "synthetic-device-password",
        },
    )
    vars_path = workspace / "group_vars" / "all" / "vars.yml"
    vars_path.write_text("---\nsccfm_region: eu\n", encoding="utf-8")
    store = VaultTokenStore(workspace)
    replacement = SavedToken(name="replacement", region="us", token="replacement-token")

    legacy_ciphertext = (workspace / "group_vars" / "all" / "vault.yml").read_bytes()
    assert store.list_tokens() == [
        SavedToken(name="legacy-active", region="eu", token="legacy-active-token")
    ]
    assert (workspace / "group_vars" / "all" / "vault.yml").read_bytes() == legacy_ciphertext
    store.save_active_and_tokens(replacement, [replacement])

    assert _view_vault(workspace) == {
        "vault_asa_branch_office_01_password": "synthetic-device-password",
        "vault_sccfm_api_token": "replacement-token",
        "sccfm_saved_tokens": [
            {
                "name": "legacy-active",
                "region": "eu",
                "token": "legacy-active-token",
            },
            {"name": "replacement", "region": "us", "token": "replacement-token"},
        ],
    }


def test_vault_store_uses_collision_safe_name_for_legacy_active_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    _write_encrypted_vault(
        workspace,
        {
            "sccfm_api_token": "legacy-active-token",
            "sccfm_saved_tokens": [
                {
                    "name": "legacy-active",
                    "region": "us",
                    "token": "different-token",
                }
            ],
        },
    )
    (workspace / "group_vars" / "all" / "vars.yml").write_text(
        "---\nsccfm_region: ci\n",
        encoding="utf-8",
    )

    assert VaultTokenStore(workspace).list_tokens() == [
        SavedToken(name="legacy-active", region="us", token="different-token"),
        SavedToken(name="legacy-active-2", region="ci", token="legacy-active-token"),
    ]


def test_vault_store_allows_explicit_update_of_synthesized_legacy_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    _write_encrypted_vault(
        workspace,
        {"sccfm_api_token": "legacy-active-token"},
    )
    (workspace / "group_vars" / "all" / "vars.yml").write_text(
        "---\nsccfm_region: us\n",
        encoding="utf-8",
    )
    store = VaultTokenStore(workspace)
    updated = SavedToken(name="legacy-active", region="us", token="updated-token")

    store.save_active_and_tokens(
        updated,
        [updated],
        preserve_omitted_active=False,
    )

    assert _view_vault(workspace) == {
        "vault_sccfm_api_token": "updated-token",
        "sccfm_saved_tokens": [{"name": "legacy-active", "region": "us", "token": "updated-token"}],
    }


@pytest.mark.parametrize(
    ("active_key", "synthetic_name"),
    [
        ("vault_sccfm_api_token", "vault-active"),
        ("sccfm_api_token", "legacy-active"),
    ],
    ids=["current", "legacy"],
)
def test_manage_tokens_can_remove_a_synthesized_active_only_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    active_key: str,
    synthetic_name: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    _write_encrypted_vault(
        workspace,
        {
            active_key: "removed-token",
            "sccfm_saved_tokens": [{"name": "kept", "region": "us", "token": "kept-token"}],
            "vault_asa_branch_password": "synthetic-device-password",
        },
    )
    (workspace / "group_vars" / "all" / "vars.yml").write_text(
        "---\nsccfm_region: us\n",
        encoding="utf-8",
    )

    class _Confirmed:
        def unsafe_ask(self) -> bool:
            return True

    monkeypatch.setattr(setup_tokens, "_resolve_examples_path", lambda path: workspace)
    monkeypatch.setattr(devkit_cli, "_ask", lambda choices, message: "token:1")
    monkeypatch.setattr(
        devkit_cli.questionary,
        "confirm",
        lambda *args, **kwargs: _Confirmed(),
    )
    synced: list[SavedToken] = []
    monkeypatch.setattr(
        devkit_cli,
        "_sync_active_token",
        lambda path, token, profiles: synced.append(cast(SavedToken, token)),
    )
    monkeypatch.setattr(devkit_cli, "_matching_cli_profiles", lambda token: ["staging"])

    devkit_cli._remove_token()

    assert _view_vault(workspace) == {
        "vault_sccfm_api_token": "kept-token",
        "sccfm_saved_tokens": [{"name": "kept", "region": "us", "token": "kept-token"}],
        "vault_asa_branch_password": "synthetic-device-password",
    }
    assert synced == [SavedToken(name="kept", region="us", token="kept-token")]


@pytest.mark.parametrize(
    ("selected_name", "expected_active_value", "expected_sync"),
    [
        ("secondary", "primary-token", []),
        (
            "primary",
            "updated-token",
            [SavedToken(name="primary", region="us", token="updated-token")],
        ),
    ],
    ids=["non-active", "active"],
)
def test_manage_token_update_preserves_active_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selected_name: str,
    expected_active_value: str,
    expected_sync: list[SavedToken],
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    primary = SavedToken(name="primary", region="us", token="primary-token")
    secondary = SavedToken(name="secondary", region="eu", token="secondary-token")
    store = VaultTokenStore(workspace)
    store.save_active_and_tokens(primary, [primary, secondary])

    class _Password:
        def unsafe_ask(self) -> str:
            return "updated-token"

    synced: list[SavedToken] = []
    monkeypatch.setattr(setup_tokens, "_resolve_examples_path", lambda path: workspace)
    selected_index = 0 if selected_name == "primary" else 1
    monkeypatch.setattr(
        devkit_cli,
        "_ask",
        lambda choices, message: f"token:{selected_index}",
    )
    monkeypatch.setattr(
        devkit_cli.questionary,
        "password",
        lambda *args, **kwargs: _Password(),
    )
    monkeypatch.setattr(
        devkit_cli,
        "_sync_active_token",
        lambda path, token, profiles: synced.append(cast(SavedToken, token)),
    )
    monkeypatch.setattr(devkit_cli, "_matching_cli_profiles", lambda token: ["staging"])

    devkit_cli._update_token()

    payload = _view_vault(workspace)
    assert payload["vault_sccfm_api_token"] == expected_active_value
    assert synced == expected_sync


def test_active_token_update_rolls_back_vault_and_surfaces_on_sync_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "project"
    workspace = root / "sccfm-ansible" / "examples"
    workspace.mkdir(parents=True)
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    config_path = tmp_path / "cli" / "config.json"
    monkeypatch.setenv("SCCFM_CONFIG", str(config_path))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    old = SavedToken(name="active", region="eu", token="old-token")
    VaultTokenStore(workspace).save_active_and_tokens(old, [old])
    _write_env_file(root, "eu", "old-token")
    _update_vars_region(workspace, "eu")
    ConfigService(config_path).save(Config(profile="staging", region="eu", api_token="old-token"))
    paths = setup_tokens._credential_state_paths(root, workspace)
    before = {path: path.read_bytes() for path in paths}

    class _Password:
        def unsafe_ask(self) -> str:
            return "new-token"

    monkeypatch.setattr(devkit_cli, "_project_root", lambda: root)
    monkeypatch.setattr(setup_tokens, "_resolve_examples_path", lambda path: workspace)
    monkeypatch.setattr(setup_tokens, "_verify_ansible_vault", lambda: None)
    monkeypatch.setattr(devkit_cli, "_ask", lambda choices, message: "token:0")
    monkeypatch.setattr(
        devkit_cli.questionary,
        "password",
        lambda *args, **kwargs: _Password(),
    )
    monkeypatch.setattr(
        setup_tokens,
        "_update_vars_region",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("injected vars failure")),
    )

    with pytest.raises(OSError, match="injected vars failure"):
        devkit_cli._update_token()

    assert {path: path.read_bytes() for path in paths} == before


@pytest.mark.parametrize(
    ("selected_name", "expected_active", "expected_sync"),
    [
        ("secondary", "primary-token", []),
        (
            "primary",
            "secondary-token",
            [SavedToken(name="secondary", region="eu", token="secondary-token")],
        ),
    ],
    ids=["non-active", "active"],
)
def test_manage_token_removal_changes_active_only_when_required(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selected_name: str,
    expected_active: str,
    expected_sync: list[SavedToken],
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    primary = SavedToken(name="primary", region="us", token="primary-token")
    secondary = SavedToken(name="secondary", region="eu", token="secondary-token")
    store = VaultTokenStore(workspace)
    store.save_active_and_tokens(primary, [primary, secondary])

    class _Confirmed:
        def unsafe_ask(self) -> bool:
            return True

    synced: list[SavedToken] = []
    monkeypatch.setattr(setup_tokens, "_resolve_examples_path", lambda path: workspace)
    selected_index = 0 if selected_name == "primary" else 1
    monkeypatch.setattr(
        devkit_cli,
        "_ask",
        lambda choices, message: f"token:{selected_index}",
    )
    monkeypatch.setattr(
        devkit_cli.questionary,
        "confirm",
        lambda *args, **kwargs: _Confirmed(),
    )
    monkeypatch.setattr(
        devkit_cli,
        "_sync_active_token",
        lambda path, token, profiles: synced.append(cast(SavedToken, token)),
    )
    monkeypatch.setattr(devkit_cli, "_matching_cli_profiles", lambda token: ["staging"])

    devkit_cli._remove_token()

    payload = _view_vault(workspace)
    assert payload["vault_sccfm_api_token"] == expected_active
    assert synced == expected_sync


def test_removing_active_token_prompts_for_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    tokens = [
        SavedToken(name="active", region="us", token="active-token"),
        SavedToken(name="eu", region="eu", token="eu-token"),
        SavedToken(name="ci", region="ci", token="ci-token"),
    ]
    VaultTokenStore(workspace).save_active_and_tokens(tokens[0], tokens)

    class _Confirmed:
        def unsafe_ask(self) -> bool:
            return True

    prompts: list[str] = []

    def choose(choices: object, message: str) -> str:
        prompts.append(message)
        return "token:0" if len(prompts) == 1 else "token:0"

    synced: list[SavedToken] = []
    monkeypatch.setattr(setup_tokens, "_resolve_examples_path", lambda path: workspace)
    monkeypatch.setattr(devkit_cli, "_ask", choose)
    monkeypatch.setattr(
        devkit_cli.questionary,
        "confirm",
        lambda *args, **kwargs: _Confirmed(),
    )
    monkeypatch.setattr(devkit_cli, "_matching_cli_profiles", lambda token: ["staging"])
    monkeypatch.setattr(
        devkit_cli,
        "_sync_active_token",
        lambda path, token, profiles: synced.append(cast(SavedToken, token)),
    )

    devkit_cli._remove_token()

    assert prompts == ["Select a token to remove:", "Select the replacement active token:"]
    assert _view_vault(workspace)["vault_sccfm_api_token"] == "ci-token"
    assert synced == [SavedToken(name="ci", region="ci", token="ci-token")]


def test_manage_tokens_prompts_for_unresolved_active_region(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    monkeypatch.delenv("SCCFM_REGION", raising=False)
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    _write_encrypted_vault(workspace, {"vault_sccfm_api_token": "eu-token"})
    (workspace / "group_vars" / "all" / "vars.yml").write_text(
        "---\nsccfm_region: \"{{ lookup('env', 'SCCFM_REGION') }}\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(setup_tokens, "_prompt_region", lambda: "eu")
    monkeypatch.setattr(setup_tokens, "_verify_ansible_vault", lambda: None)

    _store, active, tokens = devkit_cli._load_managed_tokens(workspace)

    expected = SavedToken(name="vault-active", region="eu", token="eu-token")
    assert active == expected
    assert tokens == [expected]


def test_manage_tokens_preflights_ansible_vault(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    called: list[bool] = []

    def unavailable() -> None:
        called.append(True)
        raise click.ClickException("ansible-vault not found; poetry install --with dev")

    monkeypatch.setattr(setup_tokens, "_verify_ansible_vault", unavailable)

    with pytest.raises(click.ClickException, match="poetry install --with dev"):
        devkit_cli._load_managed_tokens(workspace)

    assert called == [True]


def test_cli_profile_matching_preserves_non_default_association(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cisco_sccfm_cli import models, services

    class _ConfigService:
        def __init__(self, path: Path | None = None) -> None:
            assert path is not None

        def list_profiles(self) -> list[models.Config]:
            return [
                models.Config(profile="default", region="us", api_token="other-token"),
                models.Config(profile="staging", region="eu", api_token="active-token"),
            ]

    monkeypatch.setattr(services, "ConfigService", _ConfigService)

    assert devkit_cli._matching_cli_profiles(
        SavedToken(name="active", region="eu", token="active-token")
    ) == ["staging"]


def test_cli_profile_matching_honors_config_path_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom_config = tmp_path / "custom" / "config.json"
    monkeypatch.setenv("SCCFM_CONFIG", str(custom_config))
    ConfigService(custom_config).save(
        Config(profile="custom", region="eu", api_token="active-token")
    )

    assert devkit_cli._matching_cli_profiles(
        SavedToken(name="active", region="eu", token="active-token")
    ) == ["custom"]


@pytest.mark.parametrize(
    "vars_content",
    [
        None,
        "---\nsccfm_region: \"{{ lookup('env', 'SCCFM_REGION') }}\"\n",
        "---\nsccfm_region: invalid\n",
    ],
    ids=["missing-region-file", "unresolved-region", "invalid-region"],
)
def test_vault_store_refuses_to_discard_unrepresentable_legacy_active_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    vars_content: str | None,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    vault_path = _write_encrypted_vault(
        workspace,
        {"sccfm_api_token": "legacy-active-token"},
    )
    original = vault_path.read_bytes()
    if vars_content is not None:
        (workspace / "group_vars" / "all" / "vars.yml").write_text(
            vars_content,
            encoding="utf-8",
        )
    replacement = SavedToken(name="replacement", region="us", token="replacement-token")

    with pytest.raises(RuntimeError, match="Cannot preserve active-only sccfm_api_token"):
        VaultTokenStore(workspace).save_active_and_tokens(replacement, [replacement])

    assert vault_path.read_bytes() == original


def test_vault_store_refuses_to_discard_unrepresentable_current_active_token(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    vault_path = _write_encrypted_vault(
        workspace,
        {"vault_sccfm_api_token": "current-active-token"},
    )
    original = vault_path.read_bytes()
    replacement = SavedToken(name="replacement", region="us", token="replacement-token")

    with pytest.raises(RuntimeError, match="Cannot preserve active-only vault_sccfm_api_token"):
        VaultTokenStore(workspace).save_active_and_tokens(replacement, [replacement])

    assert vault_path.read_bytes() == original


@pytest.mark.parametrize(
    "payload",
    [
        {"vault_sccfm_api_token": "current-token"},
        {"sccfm_api_token": "legacy-token"},
    ],
    ids=["current", "legacy"],
)
def test_cli_e2e_bootstrap_accepts_current_and_legacy_vault_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, str],
) -> None:
    from cisco_sccfm_cli.e2e import _profile

    examples = tmp_path / "examples"
    vault_file = examples / "group_vars" / "all" / "vault.yml"
    vault_pass = examples / ".vault_pass"
    vars_file = examples / "group_vars" / "all" / "vars.yml"
    vault_file.parent.mkdir(parents=True)
    vault_file.write_text("encrypted-placeholder", encoding="utf-8")
    vault_pass.write_text("placeholder", encoding="utf-8")
    vars_file.write_text("sccfm_region: us\n", encoding="utf-8")
    monkeypatch.setattr(_profile, "_default_examples_dir", lambda: examples)
    monkeypatch.setattr(_profile, "_decode_vault", lambda *args: payload)

    context = _profile.bootstrap_profile(tmp_path / "cli-config")

    expected_token = next(iter(payload.values()))
    loaded = ConfigService(path=context.config_path).load(context.profile)
    assert loaded is not None
    assert loaded.api_token == expected_token


def test_cli_e2e_bootstrap_resolves_packaged_region_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cisco_sccfm_cli.e2e import _profile

    examples = tmp_path / "examples"
    vault_file = examples / "group_vars" / "all" / "vault.yml"
    vault_pass = examples / ".vault_pass"
    vars_file = examples / "group_vars" / "all" / "vars.yml"
    vault_file.parent.mkdir(parents=True)
    vault_file.write_text("encrypted-placeholder", encoding="utf-8")
    vault_pass.write_text("placeholder", encoding="utf-8")
    vars_file.write_text(
        "sccfm_region: \"{{ lookup('env', 'SCCFM_REGION') }}\"\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCCFM_REGION", "eu")
    monkeypatch.setattr(_profile, "_default_examples_dir", lambda: examples)
    monkeypatch.setattr(
        _profile,
        "_decode_vault",
        lambda *args: {"vault_sccfm_api_token": "synthetic-token"},
    )

    context = _profile.bootstrap_profile(tmp_path / "cli-config")

    assert context.region == "eu"
    loaded = ConfigService(path=context.config_path).load(context.profile)
    assert loaded is not None
    assert loaded.region == "eu"


def test_cli_e2e_vault_failure_does_not_expose_subprocess_streams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cisco_sccfm_cli.e2e import _profile

    sentinel = "sec-e2e-vault-output-sentinel"
    monkeypatch.setattr(
        _profile.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout=f"vault_sccfm_api_token: {sentinel}",
            stderr=f"partial decrypt: {sentinel}",
        ),
    )

    with pytest.raises(RuntimeError, match="could not decrypt") as exc_info:
        _profile._decode_vault(tmp_path / "vault.yml", tmp_path / ".vault_pass")

    assert sentinel not in str(exc_info.value)
    assert sentinel not in repr(exc_info.value)


def test_vault_store_removes_plaintext_temporary_file_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    vault_path = _write_encrypted_vault(
        workspace,
        {"vault_sccfm_api_token": "existing-token"},
    )
    (workspace / "group_vars" / "all" / "vars.yml").write_text(
        "---\nsccfm_region: us\n",
        encoding="utf-8",
    )
    original = vault_path.read_bytes()
    store = VaultTokenStore(workspace)
    token = SavedToken(name="test", region="us", token="synthetic-token")
    existing_payload = yaml.safe_dump(
        {"vault_sccfm_api_token": "existing-token"},
        sort_keys=False,
    )

    def failed_encrypt(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if command[1] == "view":
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=existing_payload,
                stderr="",
            )
        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr="failed",
        )

    monkeypatch.setattr("cisco_sccfm_scripts.token_store.subprocess.run", failed_encrypt)
    with pytest.raises(RuntimeError, match="ansible-vault encrypt failed"):
        store.save_active_and_tokens(token, [token])

    assert vault_path.read_bytes() == original
    assert list(vault_path.parent.glob(".vault.*.tmp")) == []


def test_vault_store_wrong_password_fails_closed_and_preserves_ciphertext(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(ansible_tmp))
    _ensure_vault_pass_headless(workspace, "correct-password")
    vault_path = _write_encrypted_vault(
        workspace,
        {"vault_sccfm_api_token": "existing-token"},
    )
    original = vault_path.read_bytes()
    (workspace / ".vault_pass").write_text("wrong-password\n", encoding="utf-8")
    store = VaultTokenStore(workspace)
    token = SavedToken(name="test", region="us", token="synthetic-token")

    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        store.save_active_and_tokens(token, [token])

    assert vault_path.read_bytes() == original
    assert list(vault_path.parent.glob(".vault.*.tmp")) == []


@pytest.mark.parametrize(
    "ciphertext",
    [
        b"not-an-ansible-vault\n",
        b"$ANSIBLE_VAULT;1.1;AES256\n0123456789abcdef\n",
    ],
    ids=["corrupt", "truncated"],
)
def test_vault_store_corrupt_vault_fails_closed_and_preserves_ciphertext(
    tmp_path: Path,
    ciphertext: bytes,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    vault_path = workspace / "group_vars" / "all" / "vault.yml"
    vault_path.parent.mkdir(parents=True)
    vault_path.write_bytes(ciphertext)
    store = VaultTokenStore(workspace)
    token = SavedToken(name="test", region="us", token="synthetic-token")

    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        store.save_active_and_tokens(token, [token])

    assert vault_path.read_bytes() == ciphertext
    assert list(vault_path.parent.glob(".vault.*.tmp")) == []


def test_malformed_decrypted_vault_does_not_expose_secret_in_exception_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _ensure_vault_pass_headless(workspace, "synthetic-password")
    vault_path = workspace / "group_vars" / "all" / "vault.yml"
    vault_path.parent.mkdir(parents=True)
    original = b"$ANSIBLE_VAULT;1.1;AES256\nsynthetic-ciphertext\n"
    vault_path.write_bytes(original)
    sentinel = "sec999-malformed-yaml-sentinel"

    monkeypatch.setattr(
        "cisco_sccfm_scripts.token_store.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=f"vault_sccfm_api_token: [{sentinel}\n",
            stderr="",
        ),
    )

    with pytest.raises(RuntimeError, match="valid YAML") as exc_info:
        VaultTokenStore(workspace).list_tokens()

    rendered = "".join(traceback.format_exception(exc_info.value))
    assert sentinel not in rendered
    assert sentinel not in repr(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert vault_path.read_bytes() == original


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
        if command[1] == "view":
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=yaml.safe_dump(
                    {
                        "vault_sccfm_api_token": "synthetic-token",
                        "sccfm_saved_tokens": [
                            {"name": "test", "region": "us", "token": "synthetic-token"}
                        ],
                    },
                    sort_keys=False,
                ),
                stderr="",
            )
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

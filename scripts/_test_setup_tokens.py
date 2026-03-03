#!/usr/bin/env python3
"""Integration tests for setup_tokens and vault-based token_store.

Backs up touched files before running, and restores them afterward
so the test is fully repeatable.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "sccfm-ansible" / "examples"
VAULT_PATH = EXAMPLES / "group_vars" / "all" / "vault.yml"
VAULT_PASS_PATH = EXAMPLES / ".vault_pass"
VARS_PATH = EXAMPLES / "group_vars" / "all" / "vars.yml"
ENV_PATH = ROOT / ".env"

_BACKUP_SUFFIX = ".test_bak"

_MANAGED_FILES = [VAULT_PATH, VAULT_PASS_PATH, VARS_PATH, ENV_PATH]


# ── Helpers ──────────────────────────────────────────────────────


def _backup(path: Path) -> None:
    if path.exists():
        dst = path.with_suffix(path.suffix + _BACKUP_SUFFIX)
        shutil.copy2(path, dst)
        print(f"  backed up  {path.name}")


def _restore(path: Path) -> None:
    bak = path.with_suffix(path.suffix + _BACKUP_SUFFIX)
    if bak.exists():
        shutil.copy2(bak, path)
        bak.unlink()
        print(f"  restored   {path.name}")
    elif path.exists():
        path.unlink()
        print(f"  removed    {path.name} (no backup existed)")


def backup_all() -> None:
    print("\n--- backup originals ---")
    for p in _MANAGED_FILES:
        _backup(p)


def restore_all() -> None:
    print("\n--- restore originals ---")
    for p in _MANAGED_FILES:
        _restore(p)


# ── Tests ────────────────────────────────────────────────────────


def test_ansible_vault_available() -> None:
    from scripts.setup_tokens import _verify_ansible_vault

    _verify_ansible_vault()
    print("PASS: ansible-vault available")


def test_vault_pass_detected() -> None:
    from scripts.setup_tokens import _ensure_vault_pass

    vp = _ensure_vault_pass(EXAMPLES)
    assert vp == VAULT_PASS_PATH, f"Expected {VAULT_PASS_PATH}, got {vp}"
    print("PASS: vault password file detected")


def test_vault_token_store_round_trip() -> None:
    """Save tokens to vault, read them back, verify contents."""
    from scripts.token_store import SavedToken, VaultTokenStore

    store = VaultTokenStore(EXAMPLES)

    # Remove vault so we start clean
    if VAULT_PATH.exists():
        VAULT_PATH.unlink()

    assert store.list_tokens() == [], "Store should start empty"

    tok1 = SavedToken(name="alpha", region="us", token="tok-aaa111")
    tok2 = SavedToken(name="beta", region="eu", token="tok-bbb222")

    # Save both tokens with tok1 as active
    store.save_active_and_tokens(tok1, [tok1, tok2])

    # Vault file should be encrypted
    first_line = VAULT_PATH.read_text().split("\n")[0]
    assert "$ANSIBLE_VAULT" in first_line, f"Not encrypted: {first_line}"

    # Read back saved tokens
    tokens = store.list_tokens()
    assert len(tokens) == 2, f"Expected 2 tokens, got {len(tokens)}"
    assert tokens[0].name == "alpha"
    assert tokens[1].name == "beta"
    assert tokens[0].token == "tok-aaa111"
    assert tokens[1].region == "eu"

    # Verify active token via ansible-vault view
    result = subprocess.run(
        ["ansible-vault", "view", str(VAULT_PATH), "--vault-password-file", str(VAULT_PASS_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Decrypt failed: {result.stderr}"
    assert "tok-aaa111" in result.stdout, "Active token not in vault"

    # Now switch active to tok2 and add a third
    tok3 = SavedToken(name="gamma", region="int", token="tok-ccc333")
    store.save_active_and_tokens(tok2, [tok1, tok2, tok3])

    tokens = store.list_tokens()
    assert len(tokens) == 3, f"Expected 3 tokens, got {len(tokens)}"

    result = subprocess.run(
        ["ansible-vault", "view", str(VAULT_PATH), "--vault-password-file", str(VAULT_PASS_PATH)],
        capture_output=True,
        text=True,
    )
    assert "tok-bbb222" in result.stdout, "Active token should be tok2 now"

    print("PASS: vault token store round-trip")
    print(f"Decrypted content:\n{result.stdout}")


def test_vars_region_updated() -> None:
    from scripts.setup_tokens import _update_vars_region

    _update_vars_region(EXAMPLES, "eu")
    content = VARS_PATH.read_text()
    assert "sccfm_region: eu" in content, "Region not updated in vars.yml"
    print("PASS: vars.yml region updated")


def test_env_file_updates_in_place() -> None:
    """Verify that existing .env is updated in-place, preserving comments."""
    from scripts.setup_tokens import _write_env_file

    seed = (
        "# Copy this file to .env and fill in your values\n"
        "export SCCFM_REGION=int\n"
        'export SCCFM_API_TOKEN="old-token"\n'
    )
    ENV_PATH.write_text(seed)

    _write_env_file(ROOT, "eu", "new-tok-456")
    content = ENV_PATH.read_text()

    assert "export SCCFM_REGION=eu" in content, "Region not updated"
    assert 'export SCCFM_API_TOKEN="new-tok-456"' in content, "Token not updated"
    assert "Copy this file" in content, "Original comment was lost"
    print("PASS: .env updated in-place (comments preserved)")


def test_env_file_created_from_example() -> None:
    """When .env doesn't exist, it should be seeded from .env.example."""
    from scripts.setup_tokens import _write_env_file

    if ENV_PATH.exists():
        ENV_PATH.unlink()

    _write_env_file(ROOT, "apj", "fresh-tok-789")
    content = ENV_PATH.read_text()

    assert "export SCCFM_REGION=apj" in content, "Region not set"
    assert 'export SCCFM_API_TOKEN="fresh-tok-789"' in content, "Token not set"
    assert "direnv" in content or "SCCFM" in content, "Missing template content"
    print("PASS: .env created from .env.example template")


# ── Headless-mode tests ─────────────────────────────────────────


def test_upsert_env_var_replaces_existing() -> None:
    """_upsert_env_var should replace an existing variable in-place."""
    from scripts.setup_tokens import _upsert_env_var

    content = "# comment\nexport FOO=old\nexport BAR=keep\n"
    result = _upsert_env_var(content, "FOO", "new")
    assert "export FOO=new" in result, "Variable not replaced"
    assert "export BAR=keep" in result, "Other variable was lost"
    assert "# comment" in result, "Comment was lost"
    print("PASS: _upsert_env_var replaces existing variable")


def test_upsert_env_var_appends_missing() -> None:
    """_upsert_env_var should append when the variable doesn't exist."""
    from scripts.setup_tokens import _upsert_env_var

    content = "# comment\nexport OTHER=value\n"
    result = _upsert_env_var(content, "NEW_VAR", "hello")
    assert "export NEW_VAR=hello" in result, "Variable not appended"
    assert "export OTHER=value" in result, "Existing variable was lost"
    print("PASS: _upsert_env_var appends missing variable")


def test_merge_token_adds_new() -> None:
    """_merge_token should add a new token when name doesn't exist."""
    from unittest.mock import MagicMock

    from scripts.setup_tokens import _merge_token
    from scripts.token_store import SavedToken

    store = MagicMock()
    store.list_tokens.return_value = [
        SavedToken(name="alpha", region="us", token="tok-aaa"),
    ]

    new_tok = SavedToken(name="beta", region="eu", token="tok-bbb")
    result = _merge_token(store, new_tok)

    assert len(result) == 2, f"Expected 2 tokens, got {len(result)}"
    names = [t.name for t in result]
    assert "alpha" in names and "beta" in names
    print("PASS: _merge_token adds new token")


def test_merge_token_replaces_existing() -> None:
    """_merge_token should replace a token with the same name."""
    from unittest.mock import MagicMock

    from scripts.setup_tokens import _merge_token
    from scripts.token_store import SavedToken

    store = MagicMock()
    store.list_tokens.return_value = [
        SavedToken(name="alpha", region="us", token="tok-old"),
        SavedToken(name="beta", region="eu", token="tok-bbb"),
    ]

    updated = SavedToken(name="alpha", region="apj", token="tok-new")
    result = _merge_token(store, updated)

    assert len(result) == 2, f"Expected 2 tokens, got {len(result)}"
    alpha = next(t for t in result if t.name == "alpha")
    assert alpha.token == "tok-new", "Token not replaced"
    assert alpha.region == "apj", "Region not updated"
    print("PASS: _merge_token replaces existing token")


def test_merge_token_empty_store() -> None:
    """_merge_token should work on an empty store."""
    from unittest.mock import MagicMock

    from scripts.setup_tokens import _merge_token
    from scripts.token_store import SavedToken

    store = MagicMock()
    store.list_tokens.return_value = []

    tok = SavedToken(name="first", region="us", token="tok-111")
    result = _merge_token(store, tok)

    assert len(result) == 1
    assert result[0].name == "first"
    print("PASS: _merge_token works on empty store")


def test_ensure_vault_pass_headless_uses_existing(tmp_path: Path) -> None:
    """When .vault_pass already exists, return it without writing."""
    from scripts.setup_tokens import _ensure_vault_pass_headless

    vault_pass = tmp_path / ".vault_pass"
    vault_pass.write_text("existing-password\n")

    result = _ensure_vault_pass_headless(tmp_path, vault_password="ignored")
    assert result == vault_pass
    assert vault_pass.read_text() == "existing-password\n", "File should not be overwritten"
    print("PASS: _ensure_vault_pass_headless uses existing file")


def test_ensure_vault_pass_headless_creates_new(tmp_path: Path) -> None:
    """When .vault_pass is missing, create it from --vault-password."""
    from scripts.setup_tokens import _ensure_vault_pass_headless

    result = _ensure_vault_pass_headless(tmp_path, vault_password="my-secret")
    assert result == tmp_path / ".vault_pass"
    assert result.read_text() == "my-secret\n"
    assert oct(result.stat().st_mode & 0o777) == "0o600", "File should be chmod 600"
    print("PASS: _ensure_vault_pass_headless creates new file")


def test_ensure_vault_pass_headless_raises_without_password(tmp_path: Path) -> None:
    """When .vault_pass is missing and no password supplied, raise."""
    import click

    from scripts.setup_tokens import _ensure_vault_pass_headless

    try:
        _ensure_vault_pass_headless(tmp_path, vault_password=None)
        raise AssertionError("Should have raised ClickException")
    except click.ClickException as exc:
        assert "--vault-password" in str(exc), f"Unexpected message: {exc}"
    print("PASS: _ensure_vault_pass_headless raises without password")


def test_headless_mode_detection() -> None:
    """Verify that main() routes to headless when --region and --api-token are set."""
    from unittest.mock import patch

    from click.testing import CliRunner

    from scripts.setup_tokens import main

    runner = CliRunner()

    # Missing --api-token → error
    result = runner.invoke(main, ["--region", "us"])
    assert result.exit_code != 0, "Should fail with only --region"
    assert "both --region and --api-token" in result.output

    # Missing --region → error
    result = runner.invoke(main, ["--api-token", "tok-123"])
    assert result.exit_code != 0, "Should fail with only --api-token"
    assert "both --region and --api-token" in result.output

    # Both supplied → should call _run_headless (mock it out)
    with patch("scripts.setup_tokens._run_headless") as mock_headless:
        result = runner.invoke(
            main,
            ["--region", "us", "--api-token", "tok-123", "--name", "myenv"],
        )
        assert result.exit_code == 0, f"Unexpected error: {result.output}"
        mock_headless.assert_called_once()
        call_kwargs = mock_headless.call_args
        assert call_kwargs.kwargs["region"] == "us"
        assert call_kwargs.kwargs["api_token"] == "tok-123"
        assert call_kwargs.kwargs["name"] == "myenv"

    print("PASS: headless mode detection works correctly")


def run_tests() -> None:
    test_ansible_vault_available()
    test_vault_pass_detected()
    test_vault_token_store_round_trip()
    test_vars_region_updated()
    test_env_file_updates_in_place()
    test_env_file_created_from_example()

    # Headless / pure-logic tests (use a temp dir)
    test_upsert_env_var_replaces_existing()
    test_upsert_env_var_appends_missing()
    test_merge_token_adds_new()
    test_merge_token_replaces_existing()
    test_merge_token_empty_store()

    with tempfile.TemporaryDirectory() as td:
        test_ensure_vault_pass_headless_uses_existing(Path(td))
    with tempfile.TemporaryDirectory() as td:
        test_ensure_vault_pass_headless_creates_new(Path(td))
    with tempfile.TemporaryDirectory() as td:
        test_ensure_vault_pass_headless_raises_without_password(Path(td))

    test_headless_mode_detection()

    print("\n=== ALL TESTS PASSED ===")


# ── Main ─────────────────────────────────────────────────────────


def main() -> None:
    backup_all()
    try:
        run_tests()
    finally:
        restore_all()


if __name__ == "__main__":
    main()

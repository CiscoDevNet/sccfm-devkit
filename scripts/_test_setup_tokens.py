#!/usr/bin/env python3
"""Integration tests for setup_tokens and vault-based token_store.

Backs up touched files before running, and restores them afterward
so the test is fully repeatable.
"""
import shutil
import subprocess
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


def run_tests() -> None:
    test_ansible_vault_available()
    test_vault_pass_detected()
    test_vault_token_store_round_trip()
    test_vars_region_updated()
    test_env_file_updates_in_place()
    test_env_file_created_from_example()
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

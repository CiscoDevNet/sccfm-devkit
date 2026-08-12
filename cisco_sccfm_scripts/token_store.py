# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Token storage backed by the encrypted Ansible Vault file.

Tokens are kept inside ``group_vars/all/vault.yml`` alongside the
active ``vault_sccfm_api_token``.  Vaults using the legacy
``sccfm_api_token`` field remain readable and are migrated the next
time they are saved.  The vault is decrypted on read and re-encrypted
on write using ``ansible-vault`` + the ``.vault_pass`` password file.

Vault structure (plaintext)::

    ---
    vault_sccfm_api_token: "<active-token>"
    sccfm_saved_tokens:
      - name: prod
        region: us
        token: "eyJ…"
      - name: staging
        region: int
        token: "eyJ…"
"""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from cisco_sccfm_core.constants import SCCFM_REGIONS, normalize_sccfm_region

_CURRENT_TOKEN_NAME = "vault-active"
_LEGACY_TOKEN_NAME = "legacy-active"
_RESERVED_TOKEN_NAMES = {"_new", "back"}
_RESERVED_TOKEN_PREFIXES = (_CURRENT_TOKEN_NAME, _LEGACY_TOKEN_NAME)
_INVALID_YAML = object()


class _TransactionVaultAbsent:
    """Marker for a Vault proven absent through the pinned transaction."""


_TRANSACTION_VAULT_ABSENT = _TransactionVaultAbsent()


class _UniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that rejects ambiguous duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    """Reject duplicate explicit keys while preserving standard YAML merge precedence."""
    explicit_keys: set[object] = set()
    for key_node, value_node in node.value:
        del value_node
        if key_node.tag == "tag:yaml.org,2002:merge":
            continue
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in explicit_keys
        except TypeError:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable key",
                key_node.start_mark,
            ) from None
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found a duplicate key",
                key_node.start_mark,
            )
        explicit_keys.add(key)

    loader.flatten_mapping(node)
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


class ActiveTokenRegionRequired(RuntimeError):
    """Raised when an active-only token needs a region for safe preservation."""


def validate_user_token_name(name: str) -> str:
    """Normalize a user-supplied label and reject token-manager sentinel names."""
    normalized = name.strip()
    if not normalized:
        raise ValueError("token name must not be empty")
    if normalized in _RESERVED_TOKEN_NAMES or any(
        normalized == prefix or normalized.startswith(f"{prefix}-")
        for prefix in _RESERVED_TOKEN_PREFIXES
    ):
        raise ValueError("token name is reserved by the interactive token manager")
    return normalized


@dataclass(frozen=True)
class SavedToken:
    """A single named API token with its associated region."""

    name: str
    region: str
    token: str = field(repr=False)

    def __post_init__(self) -> None:
        """Normalize and validate values before they can reach encrypted storage."""
        name = self.name.strip()
        token = self.token.strip()
        region = normalize_sccfm_region(self.region)
        if not name:
            raise ValueError("token name must not be empty")
        if not token:
            raise ValueError("API token must not be empty")
        if region not in SCCFM_REGIONS:
            raise ValueError("token region must be a supported SCCFM region")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "region", region)
        object.__setattr__(self, "token", token)


class VaultTokenStore:
    """Read/write helper for tokens stored in an encrypted vault file."""

    def __init__(self, examples_path: Path, migration_region: str | None = None) -> None:
        self._vault_path = examples_path / "group_vars" / "all" / "vault.yml"
        self._vault_pass_path = examples_path / ".vault_pass"
        normalized_region = normalize_sccfm_region(migration_region)
        if normalized_region is not None and normalized_region not in SCCFM_REGIONS:
            raise ValueError("migration region must be a supported SCCFM region")
        self._migration_region = normalized_region

    # ── Public API ───────────────────────────────────────────────

    @property
    def vault_exists(self) -> bool:
        """Return True if the vault file exists."""
        return self._vault_path.exists()

    @property
    def vault_pass_exists(self) -> bool:
        """Return True if the vault password file exists."""
        return self._vault_pass_path.exists()

    def list_tokens(self) -> list[SavedToken]:
        """Return all saved tokens from the vault, sorted by name."""
        data = self._decrypt_vault()
        if data is None:
            return []
        tokens = self._load_saved_tokens(data)
        tokens.extend(self._load_unsaved_active_tokens(data, tokens))
        return self._validate_token_set(tokens)

    def active_token(self) -> SavedToken | None:
        """Return the token currently selected in the Vault, if one exists."""
        data = self._decrypt_vault()
        if data is None:
            return None
        tokens = self._load_saved_tokens(data)
        tokens.extend(self._load_unsaved_active_tokens(data, tokens))
        tokens = self._validate_token_set(tokens)
        raw_active = data.get("vault_sccfm_api_token", data.get("sccfm_api_token"))
        if raw_active is None:
            return None
        if not isinstance(raw_active, str) or not raw_active.strip():
            raise RuntimeError("active SCCFM API token must be a non-empty string")
        matches = [token for token in tokens if token.token == raw_active.strip()]
        if len(matches) != 1:
            raise RuntimeError("active SCCFM API token is not represented uniquely")
        return matches[0]

    def save_active_and_tokens(
        self,
        active: SavedToken,
        all_tokens: list[SavedToken],
        *,
        preserve_omitted_active: bool = True,
    ) -> Path:
        """Update managed token fields without discarding unrelated vault data."""
        payload = self._decrypt_vault() or {}
        if preserve_omitted_active:
            saved_tokens = self._merge_unsaved_active_tokens(payload, all_tokens)
        else:
            stored_tokens = self._load_saved_tokens(payload)
            self._load_unsaved_active_tokens(payload, stored_tokens)
            saved_tokens = list(all_tokens)
        saved_tokens = self._validate_token_set(saved_tokens)
        if active not in saved_tokens:
            raise ValueError("active token must be present exactly in the saved token list")
        payload.pop("sccfm_api_token", None)
        payload["vault_sccfm_api_token"] = active.token
        payload["sccfm_saved_tokens"] = [
            {"name": t.name, "region": t.region, "token": t.token}
            for t in sorted(saved_tokens, key=lambda t: t.name)
        ]
        return self._encrypt_vault(payload)

    # ── Private helpers ──────────────────────────────────────────

    def _decrypt_vault(self) -> dict[str, object] | None:
        """Decrypt vault.yml, returning None only when the vault is absent."""
        transaction_inputs = self._transaction_decrypt_inputs()
        if transaction_inputs is _TRANSACTION_VAULT_ABSENT:
            return None
        if transaction_inputs is not None:
            vault_input, password_input, cleanup = transaction_inputs
            try:
                return self._decrypt_vault_paths(vault_input, password_input)
            finally:
                cleanup()
        if self._vault_path.is_symlink():
            raise RuntimeError("Refusing to read a symlinked vault credential file")
        if not self._vault_path.exists():
            return None
        self._validate_vault_password_file()
        if not self._vault_path.is_file():
            raise RuntimeError("Vault path must be a regular file")

        return self._decrypt_vault_paths(self._vault_path, self._vault_pass_path)

    def _decrypt_vault_paths(
        self,
        vault_path: Path,
        vault_pass_path: Path,
    ) -> dict[str, object] | None:
        """Decrypt validated input paths and parse their managed payload."""
        if not vault_path.exists():
            return None

        result = subprocess.run(
            [
                "ansible-vault",
                "view",
                str(vault_path),
                "--vault-password-file",
                str(vault_pass_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "ansible-vault could not decrypt the existing vault; refusing to overwrite it"
            )

        try:
            data: Any = yaml.load(result.stdout, Loader=_UniqueKeyLoader)
        except yaml.YAMLError:
            data = _INVALID_YAML
        if data is _INVALID_YAML:
            raise RuntimeError(
                "Decrypted vault does not contain valid YAML; refusing to overwrite it"
            )
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise RuntimeError("Decrypted vault must contain a mapping; refusing to overwrite it")
        return data

    def _transaction_decrypt_inputs(
        self,
    ) -> tuple[Path, Path, Callable[[], None]] | _TransactionVaultAbsent | None:
        """Stage pinned Vault/password bytes for pathname-based ansible-vault."""
        from cisco_sccfm_scripts import setup_tokens

        transaction = setup_tokens._active_credential_transaction
        if transaction is None or not transaction.manages(self._vault_path):
            return None
        vault_bytes = transaction.read_bytes(self._vault_path)
        if vault_bytes is None:
            if transaction.read_bytes(self._vault_pass_path) is None:
                raise RuntimeError("Vault password file is required")
            return _TRANSACTION_VAULT_ABSENT
        password_bytes = transaction.read_bytes(self._vault_pass_path)
        if password_bytes is None:
            raise RuntimeError("Vault password file is required")
        directory = Path(tempfile.mkdtemp(prefix="sccfm-vault-read-"))
        directory.chmod(0o700)
        vault_path = directory / "vault.yml"
        password_path = directory / ".vault_pass"
        vault_path.write_bytes(vault_bytes)
        password_path.write_bytes(password_bytes)
        vault_path.chmod(0o600)
        password_path.chmod(0o600)

        def cleanup() -> None:
            vault_path.unlink(missing_ok=True)
            password_path.unlink(missing_ok=True)
            directory.rmdir()

        return vault_path, password_path, cleanup

    def _validate_vault_password_file(self) -> None:
        """Require a private regular password file for every Vault operation."""
        if self._vault_pass_path.is_symlink():
            raise RuntimeError("Refusing to read a symlinked vault credential file")
        if not self._vault_pass_path.exists():
            raise RuntimeError(f"Vault password file is required: {self._vault_pass_path}")
        if not self._vault_pass_path.is_file():
            raise RuntimeError("Vault password path must be a regular file")
        if os.name == "posix" and stat.S_IMODE(self._vault_pass_path.stat().st_mode) != 0o600:
            raise RuntimeError("Vault password file must have POSIX mode 0600")

    def _load_saved_tokens(self, data: dict[str, object]) -> list[SavedToken]:
        """Validate and return saved tokens from a decrypted vault mapping."""
        raw_tokens = data.get("sccfm_saved_tokens", [])
        if not isinstance(raw_tokens, list):
            raise RuntimeError("sccfm_saved_tokens must be a list")

        tokens: list[SavedToken] = []
        for raw_token in raw_tokens:
            if not isinstance(raw_token, dict):
                raise RuntimeError("Each sccfm_saved_tokens entry must be a mapping")
            fields = {name: raw_token.get(name) for name in ("name", "region", "token")}
            if not all(isinstance(value, str) and value for value in fields.values()):
                raise RuntimeError(
                    "Each sccfm_saved_tokens entry requires non-empty name, region, and token"
                )
            try:
                tokens.append(
                    SavedToken(
                        name=fields["name"],
                        region=fields["region"],
                        token=fields["token"],
                    )
                )
            except ValueError:
                raise RuntimeError("sccfm_saved_tokens contains an invalid token entry") from None
        return self._validate_token_set(tokens)

    @staticmethod
    def _validate_token_set(tokens: list[SavedToken]) -> list[SavedToken]:
        """Require a deterministic, unambiguous set of named credentials."""
        names = [token.name for token in tokens]
        values = [token.token for token in tokens]
        if len(names) != len(set(names)):
            raise ValueError("saved token names must be unique")
        if len(values) != len(set(values)):
            raise ValueError("saved API token values must be unique")
        return sorted(tokens, key=lambda token: token.name)

    def _load_unsaved_active_tokens(
        self,
        data: dict[str, object],
        saved_tokens: list[SavedToken],
    ) -> list[SavedToken]:
        """Represent active-only current and legacy values so saves retain them."""
        unsaved: list[SavedToken] = []
        represented = list(saved_tokens)
        active_values = {
            value
            for key in ("vault_sccfm_api_token", "sccfm_api_token")
            if isinstance((value := data.get(key)), str) and value
        }
        represented_values = {token.token for token in represented}
        if len(active_values) > 1 and not active_values.issubset(represented_values):
            raise RuntimeError(
                "Vault contains distinct current and legacy active tokens without per-token "
                "regions; migrate them manually before using the token manager"
            )
        for key, base_name in (
            ("vault_sccfm_api_token", _CURRENT_TOKEN_NAME),
            ("sccfm_api_token", _LEGACY_TOKEN_NAME),
        ):
            raw_token = data.get(key)
            if raw_token is None:
                continue
            if not isinstance(raw_token, str) or not raw_token:
                raise RuntimeError(f"{key} must be a non-empty string")
            if any(token.token == raw_token for token in represented):
                continue

            token = SavedToken(
                name=self._available_token_name(base_name, represented),
                region=self._load_active_region(key),
                token=raw_token,
            )
            unsaved.append(token)
            represented.append(token)
        return unsaved

    @staticmethod
    def _available_token_name(base_name: str, tokens: list[SavedToken]) -> str:
        """Return a deterministic collision-safe synthetic token name."""
        used_names = {token.name for token in tokens}
        name = base_name
        suffix = 2
        while name in used_names:
            name = f"{base_name}-{suffix}"
            suffix += 1
        return name

    def _merge_unsaved_active_tokens(
        self,
        data: dict[str, object],
        tokens: list[SavedToken],
    ) -> list[SavedToken]:
        """Retain active-only tokens even when a caller omits them on save."""
        merged = list(tokens)
        stored_tokens = self._load_saved_tokens(data)
        for unsaved_token in self._load_unsaved_active_tokens(data, stored_tokens):
            is_represented = any(
                token.name == unsaved_token.name or token.token == unsaved_token.token
                for token in merged
            )
            if not is_represented:
                merged.append(unsaved_token)
        return merged

    def _load_active_region(self, token_key: str) -> str:
        """Load the compatibility region needed to retain an active-only token."""
        vars_path = self._vault_path.parent / "vars.yml"
        transaction_content = self._transaction_text(vars_path)
        transaction_manages = self._transaction_manages(vars_path)
        if transaction_manages:
            vars_content = transaction_content
        else:
            if vars_path.is_symlink():
                raise RuntimeError("Refusing to read a symlinked vars.yml credential companion")
            if not vars_path.exists():
                vars_content = None
            elif not vars_path.is_file():
                raise RuntimeError("vars.yml credential companion must be a regular file")
            else:
                try:
                    vars_content = vars_path.read_text(encoding="utf-8")
                except OSError:
                    raise RuntimeError(
                        f"Cannot read sccfm_region needed to preserve {token_key} from {vars_path}"
                    ) from None
        if vars_content is None:
            if self._migration_region is not None:
                return self._migration_region
            raise ActiveTokenRegionRequired(
                f"Cannot preserve active-only {token_key} without sccfm_region in {vars_path}"
            )
        try:
            data = yaml.load(vars_content, Loader=_UniqueKeyLoader)
        except yaml.YAMLError:
            data = _INVALID_YAML
        if data is _INVALID_YAML:
            raise RuntimeError(
                f"Cannot read sccfm_region needed to preserve {token_key} from {vars_path}"
            )
        if not isinstance(data, dict):
            raise RuntimeError(
                f"Cannot preserve active-only {token_key} because {vars_path} is not a YAML mapping"
            )
        raw_region = data.get("sccfm_region")
        if raw_region in {
            "{{ lookup('env', 'SCCFM_REGION') }}",
            '{{ lookup("env", "SCCFM_REGION") }}',
        }:
            raw_region = self._migration_region or os.environ.get("SCCFM_REGION")
        region = normalize_sccfm_region(raw_region if isinstance(raw_region, str) else None)
        if region is None and self._migration_region is not None:
            return self._migration_region
        if region in (None, ""):
            raise ActiveTokenRegionRequired(
                f"Cannot preserve active-only {token_key} because sccfm_region is unresolved in "
                f"{vars_path}"
            )
        if region not in SCCFM_REGIONS:
            raise RuntimeError(
                f"Cannot preserve active-only {token_key} because sccfm_region is missing or "
                f"invalid in {vars_path}"
            )
        return region

    def _encrypt_vault(self, payload: dict[str, object]) -> Path:
        """Encrypt *payload* in a private temporary file, then replace atomically."""
        group_vars_path = self._vault_path.parent.parent
        if not self._transaction_manages_vault():
            if group_vars_path.is_symlink() or self._vault_path.parent.is_symlink():
                raise RuntimeError("Refusing to write through a symlinked vault directory")
            if self._vault_path.is_symlink() or self._vault_pass_path.is_symlink():
                raise RuntimeError("Refusing to use a symlinked vault credential file")
            self._validate_vault_password_file()
            if self._vault_path.exists() and not self._vault_path.is_file():
                raise RuntimeError("Vault path must be a regular file")
            group_vars_path.mkdir(parents=True, exist_ok=True, mode=stat.S_IRWXU)
            group_vars_path.chmod(stat.S_IRWXU)
            self._vault_path.parent.mkdir(parents=True, exist_ok=True, mode=stat.S_IRWXU)
            self._vault_path.parent.chmod(stat.S_IRWXU)

        content = "---\n" + yaml.dump(payload, default_flow_style=False, sort_keys=False)
        staging_directory, staged_password_path = self._transaction_staging_directory()
        password_path = staged_password_path or self._vault_pass_path
        plaintext_descriptor, plaintext_name = tempfile.mkstemp(
            prefix=".vault.plaintext.",
            suffix=".tmp",
            dir=staging_directory,
        )
        plaintext_path = Path(plaintext_name)
        ciphertext_path: Path | None = None
        try:
            os.fchmod(plaintext_descriptor, stat.S_IRUSR | stat.S_IWUSR)
            with os.fdopen(plaintext_descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            ciphertext_descriptor, ciphertext_name = tempfile.mkstemp(
                prefix=".vault.ciphertext.",
                suffix=".tmp",
                dir=staging_directory,
            )
            ciphertext_path = Path(ciphertext_name)
            with os.fdopen(ciphertext_descriptor, "wb") as encrypted:
                os.fchmod(encrypted.fileno(), stat.S_IRUSR | stat.S_IWUSR)

            result = subprocess.run(
                [
                    "ansible-vault",
                    "encrypt",
                    str(plaintext_path),
                    "--output",
                    str(ciphertext_path),
                    "--vault-password-file",
                    str(password_path),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"ansible-vault encrypt failed:\n{result.stderr.strip()}")
            with ciphertext_path.open("rb") as encrypted:
                if not encrypted.readline(64).startswith(b"$ANSIBLE_VAULT;"):
                    raise RuntimeError("ansible-vault did not produce valid encrypted output")

            verification = subprocess.run(
                [
                    "ansible-vault",
                    "view",
                    str(ciphertext_path),
                    "--vault-password-file",
                    str(password_path),
                ],
                capture_output=True,
                text=True,
            )
            if verification.returncode != 0:
                raise RuntimeError("ansible-vault produced ciphertext that could not be verified")
            try:
                verified_payload = yaml.load(verification.stdout, Loader=_UniqueKeyLoader)
            except yaml.YAMLError:
                raise RuntimeError(
                    "ansible-vault produced ciphertext with unverifiable plaintext"
                ) from None
            if verified_payload != payload:
                raise RuntimeError("ansible-vault ciphertext did not preserve the intended payload")

            ciphertext_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            if not self._commit_transaction_ciphertext(ciphertext_path):
                os.replace(ciphertext_path, self._vault_path)
                self._vault_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            return self._vault_path
        finally:
            plaintext_path.unlink(missing_ok=True)
            if ciphertext_path is not None:
                ciphertext_path.unlink(missing_ok=True)
            if staged_password_path is not None:
                staged_password_path.unlink(missing_ok=True)
                staging_directory.rmdir()

    def _commit_transaction_ciphertext(self, ciphertext_path: Path) -> bool:
        """Use setup's pinned transaction writer when this save participates in one."""
        from cisco_sccfm_scripts import setup_tokens

        transaction = setup_tokens._active_credential_transaction
        if transaction is None:
            return False
        return transaction.write_bytes(
            self._vault_path,
            ciphertext_path.read_bytes(),
            mode=0o600,
        )

    def _transaction_staging_directory(self) -> tuple[Path, Path | None]:
        """Stage transaction secrets outside a mutable credential ancestor."""
        from cisco_sccfm_scripts import setup_tokens

        transaction = setup_tokens._active_credential_transaction
        if transaction is None or not transaction.manages(self._vault_path):
            return self._vault_path.parent, None
        password_bytes = transaction.read_bytes(self._vault_pass_path)
        if password_bytes is None:
            raise RuntimeError("Vault password file is required")
        staging_path = Path(tempfile.mkdtemp(prefix="sccfm-vault-transaction-"))
        staging_path.chmod(0o700)
        staged_password_path = staging_path / ".vault_pass"
        staged_password_path.write_bytes(password_bytes)
        staged_password_path.chmod(0o600)
        return staging_path, staged_password_path

    def _transaction_manages_vault(self) -> bool:
        from cisco_sccfm_scripts import setup_tokens

        transaction = setup_tokens._active_credential_transaction
        return transaction is not None and transaction.manages(self._vault_path)

    @staticmethod
    def _transaction_manages(path: Path) -> bool:
        from cisco_sccfm_scripts import setup_tokens

        transaction = setup_tokens._active_credential_transaction
        return transaction is not None and transaction.manages(path)

    @staticmethod
    def _transaction_text(path: Path) -> str | None:
        from cisco_sccfm_scripts import setup_tokens

        transaction = setup_tokens._active_credential_transaction
        if transaction is None or not transaction.manages(path):
            return None
        content = transaction.read_bytes(path)
        return None if content is None else content.decode("utf-8")

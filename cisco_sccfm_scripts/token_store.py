# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Token storage backed by the encrypted Ansible Vault file.

Tokens are kept inside ``group_vars/all/vault.yml`` alongside the
active ``sccfm_api_token``.  The vault is decrypted on read and
re-encrypted on write using ``ansible-vault`` + the ``.vault_pass``
password file.

Vault structure (plaintext)::

    ---
    sccfm_api_token: "<active-token>"
    sccfm_saved_tokens:
      - name: prod
        region: us
        token: "eyJ…"
      - name: staging
        region: int
        token: "eyJ…"
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml


@dataclass(frozen=True)
class SavedToken:
    """A single named API token with its associated region."""

    name: str
    region: str
    token: str


class VaultTokenStore:
    """Read/write helper for tokens stored in an encrypted vault file."""

    def __init__(self, examples_path: Path) -> None:
        self._vault_path = examples_path / "group_vars" / "all" / "vault.yml"
        self._vault_pass_path = examples_path / ".vault_pass"

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
        raw_tokens = cast(list[dict[str, str]], data.get("sccfm_saved_tokens", []))
        tokens = [SavedToken(**entry) for entry in raw_tokens]
        return sorted(tokens, key=lambda t: t.name)

    def save_active_and_tokens(
        self,
        active: SavedToken,
        all_tokens: list[SavedToken],
    ) -> Path:
        """Write the active token + full saved list, then encrypt."""
        payload: dict[str, object] = {
            "sccfm_api_token": active.token,
            "sccfm_saved_tokens": [
                {"name": t.name, "region": t.region, "token": t.token}
                for t in sorted(all_tokens, key=lambda t: t.name)
            ],
        }
        return self._encrypt_vault(payload)

    # ── Private helpers ──────────────────────────────────────────

    def _decrypt_vault(self) -> dict[str, object] | None:
        """Decrypt vault.yml and return parsed YAML, or None."""
        if not self._vault_path.exists() or not self._vault_pass_path.exists():
            return None

        result = subprocess.run(
            [
                "ansible-vault",
                "view",
                str(self._vault_path),
                "--vault-password-file",
                str(self._vault_pass_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None

        data: dict[str, object] = yaml.safe_load(result.stdout) or {}
        return data

    def _encrypt_vault(self, payload: dict[str, object]) -> Path:
        """Write *payload* as YAML to vault.yml, encrypting in-place."""
        self._vault_path.parent.mkdir(parents=True, exist_ok=True)

        content = "---\n" + yaml.dump(payload, default_flow_style=False, sort_keys=False)

        # Write plaintext, then encrypt in-place
        self._vault_path.write_text(content)
        result = subprocess.run(
            [
                "ansible-vault",
                "encrypt",
                str(self._vault_path),
                "--vault-password-file",
                str(self._vault_pass_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ansible-vault encrypt failed:\n{result.stderr.strip()}")

        return self._vault_path

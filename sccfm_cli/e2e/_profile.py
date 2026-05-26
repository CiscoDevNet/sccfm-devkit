"""Bootstrap a temporary sccfm-cli profile from the Ansible vault.

The Ansible e2e suite already manages tenant credentials via
``examples/group_vars/all/vault.yml`` (encrypted with ``.vault_pass``).
This module reuses that single source of truth: it shells out to
``ansible-vault view`` to decrypt the vault, reads the region from the
plain ``vars.yml``, and writes a temp ``sccfm-cli`` profile via the
canonical :class:`ConfigService.save` writer.  Tests then point the CLI
at the temp config via ``SCCFM_CONFIG``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from sccfm_cli.e2e._state import PhaseStateStore
from sccfm_cli.models import Config
from sccfm_cli.services import ConfigService

E2E_PROFILE_NAME = "e2e"


@dataclass(frozen=True)
class ProfileContext:
    profile: str
    config_path: Path
    region: str
    state: PhaseStateStore


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_examples_dir() -> Path:
    return _repo_root() / "sccfm-ansible" / "examples"


def _resolve_path(env_var: str, fallback: Path) -> Path:
    override = os.environ.get(env_var)
    if override:
        return Path(override)
    return fallback


def _decode_vault(vault_file: Path, vault_pass: Path) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "ansible.cli.vault",
        "view",
        str(vault_file),
        "--vault-password-file",
        str(vault_pass),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"ansible-vault view failed (rc={completed.returncode}):\n"
            f"--- stdout ---\n{completed.stdout}\n"
            f"--- stderr ---\n{completed.stderr}"
        )
    parsed = yaml.safe_load(completed.stdout) or {}
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Unexpected vault payload type: {type(parsed).__name__}")
    return parsed


def _load_plain_vars(vars_file: Path) -> dict[str, Any]:
    with vars_file.open("r", encoding="utf-8") as handle:
        parsed = yaml.safe_load(handle) or {}
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Unexpected vars.yml payload type: {type(parsed).__name__}")
    return parsed


def bootstrap_profile(config_dir: Path) -> ProfileContext:
    """Decode the vault and write a temp sccfm-cli profile.

    Raises a clear error pointing at ``scripts/setup_tokens.py`` when the
    vault inputs are missing, mirroring the Ansible runner's preflight.
    """
    examples_dir = _default_examples_dir()
    vault_file = _resolve_path("SCCFM_E2E_VAULT_FILE", examples_dir / "group_vars/all/vault.yml")
    vault_pass = _resolve_path("SCCFM_E2E_VAULT_PASS", examples_dir / ".vault_pass")
    vars_file = _resolve_path("SCCFM_E2E_VARS_FILE", examples_dir / "group_vars/all/vars.yml")

    for label, path in (
        ("vault file", vault_file),
        ("vault password file", vault_pass),
        ("vars file", vars_file),
    ):
        if not path.exists():
            raise RuntimeError(
                f"E2E credential bootstrap: {label} not found at {path}.  "
                "Run scripts/setup_tokens.py first."
            )

    plain_vars = _load_plain_vars(vars_file)
    vault_vars = _decode_vault(vault_file, vault_pass)

    region = plain_vars.get("sccfm_region")
    api_token = vault_vars.get("sccfm_api_token")
    if not region:
        raise RuntimeError(f"sccfm_region missing from {vars_file}")
    if not api_token:
        raise RuntimeError(f"sccfm_api_token missing from {vault_file}")

    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    ConfigService(path=config_path).save(
        Config(profile=E2E_PROFILE_NAME, region=region, api_token=api_token)
    )

    state = PhaseStateStore()
    return ProfileContext(
        profile=E2E_PROFILE_NAME,
        config_path=config_path,
        region=region,
        state=state,
    )

"""Shared fixtures for Ansible e2e ASA integration tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Generator

import pytest

ASA_DIR = Path(__file__).resolve().parent
PLAYBOOKS_DIR = ASA_DIR / "playbooks"
EXAMPLES_DIR = ASA_DIR.parent.parent / "examples"
VAULT_PASS = EXAMPLES_DIR / ".vault_pass"


def run_playbook(name: str) -> subprocess.CompletedProcess[str]:
    """Run a playbook from the playbooks/ directory and return the result.

    Raises AssertionError with the full Ansible output on failure.
    """
    playbook = PLAYBOOKS_DIR / name
    if not playbook.exists():
        raise AssertionError(f"Playbook not found: {playbook}")

    env = os.environ.copy()
    env.setdefault("ANSIBLE_COLLECTIONS_PATH", str(Path.home() / ".ansible/collections"))

    cmd = [
        sys.executable,
        "-m",
        "ansible.cli.playbook",
        "-i",
        "localhost,",
        "-c",
        "local",
        "-e",
        f"ansible_python_interpreter={sys.executable}",
        str(playbook),
        "--vault-password-file",
        str(VAULT_PASS),
    ]
    try:
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=600, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            f"Playbook '{name}' timed out after {exc.timeout} seconds:\n"
            f"--- stdout ---\n{exc.stdout or ''}\n"
            f"--- stderr ---\n{exc.stderr or ''}"
        ) from exc

    if result.returncode != 0:
        raise AssertionError(
            f"Playbook '{name}' failed (rc={result.returncode}):\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
    return result


@pytest.fixture(scope="session", autouse=True)
def lifecycle_cleanup() -> Generator[None, None, None]:
    """Pre-clean before tests, and always clean up after — even on failure."""
    try:
        run_playbook("cleanup.yml")
    except AssertionError as e:
        pytest.exit(f"Pre-test cleanup failed, aborting suite: {e}", returncode=1)
    yield
    run_playbook("cleanup.yml")

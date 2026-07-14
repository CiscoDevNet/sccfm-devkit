# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Shared fixtures for Ansible e2e FTD integration tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Generator

import pytest

from cisco_sccfm_scripts.cleanup_ftd_manager import (
    FtdManagerCleanupError,
    cleanup_manager_from_environment,
)

FTD_DIR = Path(__file__).resolve().parent
PLAYBOOKS_DIR = FTD_DIR / "playbooks"
EXAMPLES_DIR = FTD_DIR.parent.parent / "examples"
VAULT_PASS = EXAMPLES_DIR / ".vault_pass"


def _cleanup_timeout() -> int:
    """Allow the cleanup playbook to finish its configured polling window."""
    retries = int(os.getenv("FTD_CLEANUP_RETRIES", "60"))
    delay = int(os.getenv("FTD_REGISTRATION_DELAY", "10"))
    return max(900, (retries * delay) + 120)


def _decode_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_playbook(name: str, timeout: int = 600) -> subprocess.CompletedProcess[str]:
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
            cmd, env=env, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            f"Playbook '{name}' timed out after {exc.timeout} seconds:\n"
            f"--- stdout ---\n{_decode_output(exc.stdout)}\n"
            f"--- stderr ---\n{_decode_output(exc.stderr)}"
        ) from exc

    if result.returncode != 0:
        raise AssertionError(
            f"Playbook '{name}' failed (rc={result.returncode}):\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
    return result


def cleanup_registration_fixture() -> None:
    """Remove the SCCFM record, then reset the persistent appliance."""
    run_playbook("cleanup.yml", timeout=_cleanup_timeout())
    cleanup_manager_from_environment()


@pytest.fixture(scope="session", autouse=True)
def lifecycle_cleanup() -> Generator[None, None, None]:
    """Pre-clean before tests, and always clean up after -- even on failure."""
    try:
        cleanup_registration_fixture()
    except (AssertionError, FtdManagerCleanupError) as exc:
        pytest.exit(f"Pre-test cleanup failed, aborting suite: {exc}", returncode=1)
    yield
    cleanup_registration_fixture()

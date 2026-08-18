# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from cisco_sccfm_core.models.profile import Profile
from cisco_sccfm_core.services.profile_service import ProfileService
from cisco_sccfm_scripts.import_legacy_vault import import_profiles, read_legacy_profiles


def test_should_read_saved_profiles_without_modifying_vault(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    vault_path = tmp_path / "vault.yml"
    password_path = tmp_path / ".vault_pass"
    vault_path.write_text("$ANSIBLE_VAULT;1.1;AES256\nunchanged\n")
    password_path.write_text("password\n")
    before = vault_path.read_bytes()
    decrypted = """---
sccfm_saved_tokens:
  - name: default
    region: us
    token: token-one
  - name: lab
    region: eu
    token: token-two
"""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, decrypted, ""),
    )

    profiles = read_legacy_profiles(vault_path, password_path, None)

    assert profiles == [
        Profile(profile="default", region="us", api_token="token-one"),
        Profile(profile="lab", region="eu", api_token="token-two"),
    ]
    assert vault_path.read_bytes() == before


def test_should_import_without_overwriting_existing_profiles(tmp_path: Path) -> None:
    service = ProfileService(tmp_path / "config.json")
    service.save(Profile(profile="default", region="us", api_token="existing"))

    imported, skipped = import_profiles(
        [
            Profile(profile="default", region="eu", api_token="replacement"),
            Profile(profile="lab", region="eu", api_token="new-token"),
        ],
        service,
        overwrite=False,
    )

    assert imported == ["lab"]
    assert skipped == ["default"]
    assert service.load("default") == Profile(profile="default", region="us", api_token="existing")


def test_should_import_single_active_legacy_token(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    vault_path = tmp_path / "vault.yml"
    password_path = tmp_path / ".vault_pass"
    vars_path = tmp_path / "vars.yml"
    vault_path.write_text("encrypted")
    password_path.write_text("password")
    vars_path.write_text("sccfm_region: apj\n")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, "sccfm_api_token: legacy-token\n", ""
        ),
    )

    assert read_legacy_profiles(vault_path, password_path, vars_path) == [
        Profile(profile="default", region="apj", api_token="legacy-token")
    ]

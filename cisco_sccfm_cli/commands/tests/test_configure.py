# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.services import ConfigService


def test_should_create_new_profile(cli_runner: CliRunner, config_path: Path) -> None:
    """Configure command should create a new profile with provided credentials."""
    result = cli_runner.invoke(
        cli,
        [
            "--profile",
            "lab",
            "configure",
            "--region",
            "eu",
            "--api-token",
            "token-xyz",
            "--config-path",
            str(config_path),
        ],
    )

    assert result.exit_code == 0

    service = ConfigService(path=config_path)
    stored = service.load("lab")
    assert stored is not None
    assert stored.region == "eu"
    assert stored.api_token == "token-xyz"


def test_should_allow_modification_of_existing_profile(
    cli_runner: CliRunner, config_path: Path
) -> None:
    """Configure command should succeed when called multiple times on same profile."""
    profile_name = "prod"
    old_region = "eu"
    new_region = "apj"
    old_token = "burak-crush-pineapple"
    new_token = "burak-crush-papaya"
    result1 = cli_runner.invoke(
        cli,
        [
            "--profile",
            profile_name,
            "configure",
            "--region",
            old_region,
            "--api-token",
            old_token,
            "--config-path",
            str(config_path),
        ],
    )
    assert result1.exit_code == 0, f"Configure failed: {result1.output}"
    stored = ConfigService(path=config_path).load(profile_name)
    assert stored is not None, (
        f"Profile {profile_name} not found. Available: "
        f"{ConfigService(path=config_path).list_profiles()}"
    )
    assert stored.region == old_region
    assert stored.api_token == old_token

    result2 = cli_runner.invoke(
        cli,
        [
            "--profile",
            profile_name,
            "configure",
            "--region",
            new_region,
            "--api-token",
            new_token,
            "--config-path",
            str(config_path),
        ],
    )
    updated_stored = ConfigService(path=config_path).load(profile_name)
    assert updated_stored is not None
    assert updated_stored.region == new_region
    assert updated_stored.api_token == new_token

    assert result2.exit_code == 0


def test_should_normalize_legacy_region_aliases(cli_runner: CliRunner, config_path: Path) -> None:
    """Configure should normalize case and legacy aliases to the canonical region value."""
    result = cli_runner.invoke(
        cli,
        [
            "--profile",
            "lab",
            "configure",
            "--region",
            "AUS",
            "--api-token",
            "token-xyz",
            "--config-path",
            str(config_path),
        ],
    )

    assert result.exit_code == 0

    stored = ConfigService(path=config_path).load("lab")
    assert stored is not None
    assert stored.region == "au"


def test_should_prompt_for_token_without_echoing_it(
    cli_runner: CliRunner, config_path: Path
) -> None:
    result = cli_runner.invoke(
        cli,
        [
            "configure",
            "--region",
            "us",
            "--config-path",
            str(config_path),
        ],
        input="prompted-secret\n",
    )

    assert result.exit_code == 0
    assert "prompted-secret" not in result.output
    stored = ConfigService(path=config_path).load("default")
    assert stored is not None
    assert stored.api_token == "prompted-secret"

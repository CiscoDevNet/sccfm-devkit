# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hmac
import os
import stat
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.commands.configure import ConfigureCommand
from cisco_sccfm_cli.models import Config
from cisco_sccfm_cli.services import ConfigService

_API_TOKEN_ENVVAR = "SCCFM_API_TOKEN"
POSIX_ONLY = pytest.mark.skipif(
    os.name != "posix",
    reason="POSIX permission bits are not portable to this platform",
)


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
    assert "process listings" in result.stderr
    _assert_not_exposed(result.output, "token-xyz")

    service = ConfigService(path=config_path)
    stored = service.load("lab")
    assert stored is not None
    assert stored.region == "eu"
    _assert_same_secret(stored.api_token, "token-xyz")


def test_should_read_api_token_from_environment(cli_runner: CliRunner, config_path: Path) -> None:
    """Configure should avoid argv exposure by accepting an environment token."""
    api_token = "sec005-environment-token-63ae1"
    result = cli_runner.invoke(
        cli,
        ["--profile", "lab", "configure", "--region", "eu"],
        env={_API_TOKEN_ENVVAR: api_token},
    )

    assert result.exit_code == 0
    assert "process listings" not in result.output
    _assert_not_exposed(result.output, api_token)

    stored = ConfigService(path=config_path).load("lab")
    assert stored is not None
    _assert_same_secret(stored.api_token, api_token)


@POSIX_ONLY
def test_configure_repairs_unsafe_file_and_preserves_other_profiles(
    cli_runner: CliRunner,
    config_path: Path,
) -> None:
    """The explicit local-write command may repair storage before updating it."""
    existing = Config(profile="existing", region="us", api_token="existing-example-token")
    service = ConfigService(path=config_path)
    service.save(existing)
    config_path.chmod(0o644)
    parent_mode = stat.S_IMODE(config_path.parent.stat().st_mode)

    result = cli_runner.invoke(
        cli,
        ["--profile", "added", "configure", "--region", "eu"],
        env={_API_TOKEN_ENVVAR: "added-example-token"},
    )

    assert result.exit_code == 0, result.output
    assert stat.S_IMODE(config_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(config_path.parent.stat().st_mode) == parent_mode
    assert service.load(existing.profile) == existing
    assert service.load("added") == Config(
        profile="added", region="eu", api_token="added-example-token"
    )


def test_should_prompt_for_api_token_without_echoing_it(
    cli_runner: CliRunner,
    config_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Configure should use a hidden prompt when no non-interactive source is supplied."""
    api_token = "sec005-prompt-token-91bc2"
    monkeypatch.setattr(ConfigureCommand, "_can_prompt", lambda self: True)

    result = cli_runner.invoke(
        cli,
        ["--profile", "lab", "configure", "--region", "eu"],
        input=f"{api_token}\n",
        env={_API_TOKEN_ENVVAR: None},
    )

    assert result.exit_code == 0
    assert "API token:" in result.output
    _assert_not_exposed(result.output, api_token)

    stored = ConfigService(path=config_path).load("lab")
    assert stored is not None
    _assert_same_secret(stored.api_token, api_token)


def test_should_redact_prompted_api_token_from_save_failures(
    cli_runner: CliRunner,
    config_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Prompted tokens should enter command-scoped redaction before configuration is saved."""
    api_token = "sec005-prompt-failure-token-a471e"
    monkeypatch.setattr(ConfigureCommand, "_can_prompt", lambda self: True)

    def fail_save(self: ConfigService, config: Config) -> None:
        raise RuntimeError(f"Synthetic save failure involving {config.api_token}")

    monkeypatch.setattr(ConfigService, "save", fail_save)

    result = cli_runner.invoke(
        cli,
        [
            "--profile",
            "lab",
            "configure",
            "--region",
            "eu",
            "--config-path",
            str(config_path),
        ],
        input=f"{api_token}\n",
        env={_API_TOKEN_ENVVAR: None},
    )

    assert result.exit_code != 0
    assert "<redacted>" in result.output
    _assert_not_exposed(result.output, api_token)
    _assert_not_exposed(repr(result.exception), api_token)


def test_should_fail_clearly_without_api_token_in_non_interactive_session(
    cli_runner: CliRunner,
    config_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Configure should not attempt to read a secret from redirected stdin."""
    monkeypatch.setattr(ConfigureCommand, "_can_prompt", lambda self: False)

    result = cli_runner.invoke(
        cli,
        ["configure", "--region", "eu", "--config-path", str(config_path)],
        env={_API_TOKEN_ENVVAR: None},
    )

    assert result.exit_code == 2
    assert f"Set {_API_TOKEN_ENVVAR}" in result.output
    assert "hidden prompt" in result.output


def test_should_reject_blank_api_token(cli_runner: CliRunner, config_path: Path) -> None:
    """Configure should reject environment tokens containing only whitespace."""
    result = cli_runner.invoke(
        cli,
        ["configure", "--region", "eu", "--config-path", str(config_path)],
        env={_API_TOKEN_ENVVAR: "   "},
    )

    assert result.exit_code == 2
    assert "API token cannot be empty" in result.output


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
    _assert_same_secret(stored.api_token, old_token)

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
    _assert_same_secret(updated_stored.api_token, new_token)

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


def _assert_not_exposed(output: str, api_token: str) -> None:
    if api_token in output:
        raise AssertionError("API token was exposed in command output")


def _assert_same_secret(actual: str, expected: str) -> None:
    if not hmac.compare_digest(actual, expected):
        raise AssertionError("Stored API token did not match the supplied token")

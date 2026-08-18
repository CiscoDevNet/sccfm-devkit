#!/usr/bin/env python3

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Import SCCFM API profiles from the legacy Ansible Vault token store."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, cast

import click
import yaml
from rich.console import Console

from cisco_sccfm_core.models.profile import Profile
from cisco_sccfm_core.services.profile_service import ProfileService

console = Console()


def read_legacy_profiles(
    vault_path: Path,
    vault_password_path: Path,
    vars_path: Path | None,
) -> list[Profile]:
    """Decrypt a legacy vault and return validated profiles without modifying it."""
    _require_file(vault_path, "Legacy vault")
    _require_file(vault_password_path, "Vault password file")
    completed = subprocess.run(
        [
            "ansible-vault",
            "view",
            str(vault_path),
            "--vault-password-file",
            str(vault_password_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise click.ClickException(f"Could not decrypt legacy vault: {completed.stderr.strip()}")

    payload = _load_mapping(completed.stdout, vault_path)
    saved = cast(list[dict[str, Any]], payload.get("sccfm_saved_tokens", []))
    if saved:
        return [_profile_from_saved_token(item) for item in saved]

    token = payload.get("sccfm_api_token")
    if not isinstance(token, str) or not token.strip():
        return []
    if vars_path is None:
        raise click.ClickException(
            "Legacy vault contains an active token but no saved profiles; --vars-file is required."
        )
    _require_file(vars_path, "Legacy vars file")
    variables = _load_mapping(vars_path.read_text(encoding="utf-8"), vars_path)
    region = variables.get("sccfm_region")
    if not isinstance(region, str) or not region.strip():
        raise click.ClickException(f"sccfm_region is missing from {vars_path}")
    return [Profile(profile="default", region=region.strip(), api_token=token.strip())]


def import_profiles(
    profiles: list[Profile],
    service: ProfileService,
    overwrite: bool,
) -> tuple[list[str], list[str]]:
    """Import profiles, returning imported and skipped profile names."""
    imported: list[str] = []
    skipped: list[str] = []
    for profile in profiles:
        if service.load(profile.profile) is not None and not overwrite:
            skipped.append(profile.profile)
            continue
        service.save(profile)
        imported.append(profile.profile)
    return imported, skipped


def _profile_from_saved_token(item: dict[str, Any]) -> Profile:
    required = ("name", "region", "token")
    missing = [key for key in required if not isinstance(item.get(key), str) or not item[key]]
    if missing:
        raise click.ClickException(
            f"Legacy saved token is missing valid fields: {', '.join(missing)}"
        )
    return Profile(
        profile=cast(str, item["name"]).strip(),
        region=cast(str, item["region"]).strip(),
        api_token=cast(str, item["token"]).strip(),
    )


def _load_mapping(content: str, source: Path) -> dict[str, Any]:
    parsed = yaml.safe_load(content) or {}
    if not isinstance(parsed, dict):
        raise click.ClickException(f"Expected a YAML mapping in {source}")
    return cast(dict[str, Any], parsed)


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise click.ClickException(f"{label} not found: {path}")


@click.command(help="Import SCCFM profiles from the legacy Ansible Vault token store.")
@click.option(
    "--vault-file",
    type=click.Path(path_type=Path, exists=True, dir_okay=False, resolve_path=True),
    default=Path("sccfm-ansible/examples/group_vars/all/vault.yml"),
    show_default=True,
)
@click.option(
    "--vault-password-file",
    type=click.Path(path_type=Path, exists=True, dir_okay=False, resolve_path=True),
    default=Path("sccfm-ansible/examples/.vault_pass"),
    show_default=True,
)
@click.option(
    "--vars-file",
    type=click.Path(path_type=Path, exists=True, dir_okay=False, resolve_path=True),
    default=Path("sccfm-ansible/examples/group_vars/all/vars.yml"),
    show_default=True,
)
@click.option(
    "--config-path",
    type=click.Path(path_type=Path, dir_okay=False, resolve_path=True),
    default=None,
    help="Canonical SCCFM config path (defaults to ~/.sccfm-cli/config.json).",
)
@click.option("--overwrite", is_flag=True, help="Replace profiles with matching names.")
def main(
    vault_file: Path,
    vault_password_file: Path,
    vars_file: Path,
    config_path: Path | None,
    overwrite: bool,
) -> None:
    """Import legacy profiles without changing the source vault."""
    profiles = read_legacy_profiles(vault_file, vault_password_file, vars_file)
    imported, skipped = import_profiles(profiles, ProfileService(config_path), overwrite)
    if not profiles:
        console.print("[yellow]No SCCFM API tokens found in the legacy vault.[/yellow]")
        return
    if imported:
        console.print(f"[green]Imported profiles:[/green] {', '.join(sorted(imported))}")
    if skipped:
        console.print(
            f"[yellow]Skipped existing profiles:[/yellow] {', '.join(sorted(skipped))} "
            "(use --overwrite to replace them)"
        )
    console.print("[dim]The legacy vault and password file were not modified.[/dim]")


if __name__ == "__main__":
    main()

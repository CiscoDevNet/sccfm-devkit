#!/usr/bin/env python3
"""Setup for SCCFM API tokens, .env, and Ansible Vault.

Runs **interactively** by default (prompts for region, token, etc.).
Supply ``--region`` and ``--api-token`` to run **headless** — suitable
for CI pipelines and scripted workflows.

Manages a local token store so tokens can be reused across setups.
Creates / updates:
  - .env              (SCCFM_REGION, SCCFM_API_TOKEN)
  - .vault_pass       (vault password file)
  - group_vars/all/vars.yml   (sccfm_region)
  - group_vars/all/vault.yml  (encrypted sccfm_api_token)
  - ~/.sccfm-cli/config.json  (CLI profile)

Examples::

    # Interactive (default)
    python scripts/setup_tokens.py

    # Headless — minimal
    python scripts/setup_tokens.py --region us --api-token eyJ…

    # Headless — all options
    python scripts/setup_tokens.py \\
        --region int --api-token eyJ… \\
        --name staging --profile staging \\
        --vault-password s3cret
"""

from __future__ import annotations

import re
import stat
import subprocess
from pathlib import Path

import click
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sccfm_core.constants import SCCFM_REGIONS
from scripts.token_store import SavedToken, VaultTokenStore

_REGION_DESCRIPTIONS: dict[str, str] = {
    "int": "Internal (Staging)",
    "us": "United States",
    "eu": "Europe",
    "apj": "Asia Pacific & Japan",
    "au": "Australia",
    "uae": "UAE",
    "in": "India",
    "ci": "CI",
}
_REGIONS: dict[str, str] = {region: _REGION_DESCRIPTIONS[region] for region in SCCFM_REGIONS}

_DEFAULT_EXAMPLES_PATH = "sccfm-ansible/examples"
_ENV_EXAMPLE = ".env.example"

console = Console()


def _project_root() -> Path:
    """Return the repository root (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent


# ── Path resolution ──────────────────────────────────────────────


def _resolve_examples_path(path: str | None) -> Path:
    """Return the absolute examples directory, raising if not found."""
    if path:
        resolved = Path(path).resolve()
        if not resolved.is_dir():
            raise click.ClickException(f"Directory not found: {resolved}")
        return resolved

    default = Path.cwd() / _DEFAULT_EXAMPLES_PATH
    if default.is_dir():
        return default.resolve()

    # Maybe the user already cd'd into the examples dir
    cwd = Path.cwd()
    if (cwd / "group_vars").is_dir() and (cwd / ".vault_pass.example").exists():
        return cwd.resolve()

    raise click.ClickException(
        "Could not locate the ansible examples directory.\n"
        "Run from the project root or pass --path explicitly."
    )


# ── Ansible-vault availability ───────────────────────────────────


def _verify_ansible_vault() -> None:
    try:
        subprocess.run(
            ["ansible-vault", "--version"],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError:
        raise click.ClickException(
            "ansible-vault not found. Install ansible-core:\n" "  poetry install --with dev"
        )


# ── Token selection / creation ───────────────────────────────────


def _select_or_create_token(store: VaultTokenStore) -> tuple[SavedToken, list[SavedToken]]:
    """Let the user pick a saved token or create a new one.

    Returns the selected token and the full list of all tokens (for re-saving).
    """
    saved = store.list_tokens()
    if saved:
        return _choose_from_saved_or_new(saved)
    new_token = _prompt_new_token()
    return new_token, [new_token]


def _choose_from_saved_or_new(
    saved: list[SavedToken],
) -> tuple[SavedToken, list[SavedToken]]:
    """Present saved tokens and an 'Add new' option."""
    choices: list[questionary.Choice] = [
        questionary.Choice(
            title=f"{t.name:<20} region={t.region}  token=…{t.token[-6:]}",
            value=t.name,
        )
        for t in saved
    ]
    choices.append(questionary.Choice(title="+ Add a new token", value="_new"))

    answer: str | None = questionary.select(
        "Select a saved token or add a new one:",
        choices=choices,
    ).ask()

    if answer is None:
        raise click.Abort()

    if answer == "_new":
        new_token = _prompt_new_token()
        all_tokens = [t for t in saved if t.name != new_token.name]
        all_tokens.append(new_token)
        return new_token, all_tokens

    selected = next((t for t in saved if t.name == answer), None)
    if selected is None:
        raise click.ClickException(f"Token '{answer}' not found in vault.")
    return selected, saved


def _prompt_new_token() -> SavedToken:
    """Interactively gather a new token."""
    region = _prompt_region()
    api_token = _prompt_token()
    name = _prompt_token_name()
    return SavedToken(name=name, region=region, token=api_token)


# ── Interactive prompts ──────────────────────────────────────────


def _prompt_region() -> str:
    """Display region table and prompt for a choice (accepts name or number)."""
    table = Table(title="Available Regions", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Region", style="bold")
    table.add_column("Description")

    region_keys = list(_REGIONS.keys())
    for idx, (key, desc) in enumerate(_REGIONS.items(), 1):
        table.add_row(str(idx), key, desc)

    console.print()
    console.print(table)

    while True:
        choice: str = click.prompt("\nSelect region (name or #)", default="us")
        choice = choice.strip().lower()

        # Accept by number
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(region_keys):
                return region_keys[idx - 1]

        # Accept by name
        if choice in region_keys:
            return choice

        console.print(f"[red]Invalid choice '{choice}'. Enter a region name or number.[/red]")


def _prompt_token() -> str:
    """Ask the user to paste their API token (hidden input)."""
    token: str = click.prompt("\nPaste your SCCFM API token")
    token = token.strip()
    if not token:
        raise click.ClickException("API token cannot be empty.")
    return token


def _prompt_token_name() -> str:
    """Ask for a label to identify this token."""
    name: str = click.prompt(
        "\nName for this token (for your reference)",
        default="default",
    )
    return name.strip()


# ── .env file management ────────────────────────────────────────


def _upsert_env_var(content: str, var: str, value: str) -> str:
    """Replace ``export VAR=…`` in *content*, or append if not present."""
    pattern = rf"^(export\s+){var}=.*$"
    replacement = f"export {var}={value}"
    updated, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
    if count == 0:
        updated = updated.rstrip() + f"\n{replacement}\n"
    return updated


def _write_env_file(root: Path, region: str, api_token: str) -> Path:
    """Create or update the root .env with region and token.

    If ``.env`` exists, the two variables are updated in-place so that
    comments and other entries are preserved.  If it doesn't exist,
    ``.env.example`` is used as the starting template.
    """
    env_path = root / ".env"
    example_path = root / _ENV_EXAMPLE

    if env_path.exists():
        content = env_path.read_text()
    elif example_path.exists():
        content = example_path.read_text()
    else:
        content = (
            "# Auto-generated by setup-tokens — do not commit\n"
            "# The .env file is gitignored and loaded automatically by direnv\n\n"
        )

    content = _upsert_env_var(content, "SCCFM_REGION", region)
    content = _upsert_env_var(content, "SCCFM_API_TOKEN", f'"{api_token}"')
    env_path.write_text(content)
    console.print(f"[green]Updated .env file:[/green] {env_path}")
    return env_path


# ── CLI config management ────────────────────────────────────────


def _update_cli_config(region: str, api_token: str, profile: str = "default") -> None:
    """Update the sccfm-cli config so CLI commands use the same token."""
    from sccfm_cli.models import Config
    from sccfm_cli.services import ConfigService

    config = Config(profile=profile, region=region, api_token=api_token)
    ConfigService().save(config)
    console.print(f"[green]Updated CLI config profile '{profile}'[/green]")


# ── Vault password management ────────────────────────────────────


def _ensure_vault_pass(examples_path: Path) -> Path:
    """Return the vault password file, creating it interactively if needed."""
    vault_pass_path = examples_path / ".vault_pass"

    if vault_pass_path.exists():
        console.print(f"\n[dim]Using existing vault password file: {vault_pass_path}[/dim]")
        return vault_pass_path

    console.print("\n[yellow]No vault password file found — creating one now.[/yellow]")
    password: str = click.prompt(
        "Enter a vault password",
        hide_input=True,
        confirmation_prompt=True,
    )
    if not password.strip():
        raise click.ClickException("Vault password cannot be empty.")

    vault_pass_path.write_text(password.strip() + "\n")
    vault_pass_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # chmod 600
    console.print(f"[green]Created vault password file:[/green] {vault_pass_path}")
    return vault_pass_path


def _ensure_vault_pass_headless(examples_path: Path, vault_password: str | None) -> Path:
    """Return the vault password file, creating it from *vault_password*
    if it does not already exist.  No interactive prompts.
    """
    vault_pass_path = examples_path / ".vault_pass"

    if vault_pass_path.exists():
        console.print(f"[dim]Using existing vault password file: {vault_pass_path}[/dim]")
        return vault_pass_path

    if not vault_password:
        raise click.ClickException(
            "No vault password file found and --vault-password was not supplied."
        )

    vault_pass_path.write_text(vault_password.strip() + "\n")
    vault_pass_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # chmod 600
    console.print(f"[green]Created vault password file:[/green] {vault_pass_path}")
    return vault_pass_path


def _merge_token(store: VaultTokenStore, token: SavedToken) -> list[SavedToken]:
    """Merge *token* into the existing saved list, replacing by name."""
    existing = store.list_tokens()
    merged = [t for t in existing if t.name != token.name]
    merged.append(token)
    return merged


# ── vars.yml management ─────────────────────────────────────────


def _update_vars_region(examples_path: Path, region: str) -> None:
    """Set sccfm_region in group_vars/all/vars.yml, preserving other content."""
    vars_path = examples_path / "group_vars" / "all" / "vars.yml"
    vars_path.parent.mkdir(parents=True, exist_ok=True)

    if vars_path.exists():
        content = vars_path.read_text()
        if re.search(r"^sccfm_region:.*$", content, flags=re.MULTILINE):
            updated = re.sub(
                r"^sccfm_region:.*$",
                f"sccfm_region: {region}",
                content,
                flags=re.MULTILINE,
            )
        else:
            updated = content.rstrip() + f"\nsccfm_region: {region}\n"
        vars_path.write_text(updated)
    else:
        vars_path.write_text(
            "---\n"
            "# Plain variables (not sensitive)\n"
            "# These can be committed to version control\n"
            "\n"
            "# SCCFM connection settings\n"
            f"sccfm_region: {region}\n"
        )

    console.print(f"[green]Set region to '{region}' in:[/green] {vars_path}")


# ── Headless logic ───────────────────────────────────────────────


def _run_headless(
    region: str,
    api_token: str,
    name: str,
    profile: str,
    vault_password: str | None,
    path: str | None,
) -> None:
    """Execute the full setup without any interactive prompts."""
    root = _project_root()
    examples_path = _resolve_examples_path(path)
    console.print(f"[dim]Examples directory: {examples_path}[/dim]")

    _verify_ansible_vault()

    # ── Vault password ───────────────────────────────────────────
    vault_pass_path = _ensure_vault_pass_headless(examples_path, vault_password)

    # ── Build token ──────────────────────────────────────────────
    selected = SavedToken(name=name, region=region, token=api_token)

    # ── Merge with existing saved tokens ─────────────────────────
    store = VaultTokenStore(examples_path)
    all_tokens = _merge_token(store, selected)

    # ── Write files ──────────────────────────────────────────────
    env_path = _write_env_file(root, region, api_token)
    _update_vars_region(examples_path, region)
    vault_path = store.save_active_and_tokens(selected, all_tokens)
    console.print(f"[green]Encrypted vault file updated:[/green] {vault_path}")
    _update_cli_config(region, api_token, profile=profile)

    # ── Summary ──────────────────────────────────────────────────
    summary = Table(title="Setup Complete", show_header=False, border_style="green")
    summary.add_column("Key", style="bold")
    summary.add_column("Value")
    summary.add_row("Token", name)
    summary.add_row("Region", region)
    summary.add_row("CLI Profile", profile)
    summary.add_row(".env file", str(env_path))
    summary.add_row("Vault file", str(vault_path))
    summary.add_row("Vault password", str(vault_pass_path))
    summary.add_row("CLI config", "~/.sccfm-cli/config.json")

    console.print()
    console.print(summary)


# ── CLI entry point ──────────────────────────────────────────────

_VALID_REGIONS = tuple(_REGIONS)


@click.command(
    help="Setup SCCFM API tokens, .env, and Ansible Vault.\n\n"
    "Runs interactively by default.  Supply --region and --api-token "
    "to run in headless mode (no prompts).",
)
@click.option(
    "--region",
    "-r",
    default=None,
    type=click.Choice(_VALID_REGIONS, case_sensitive=False),
    help="SCCFM region.  Enables headless mode when combined with --api-token.",
)
@click.option(
    "--api-token",
    "-t",
    default=None,
    help="SCCFM API token.  Enables headless mode when combined with --region.",
)
@click.option(
    "--name",
    "-n",
    default="default",
    show_default=True,
    help="Label for this token in the vault store (headless only).",
)
@click.option(
    "--profile",
    "-p",
    default="default",
    show_default=True,
    help="CLI config profile name to update (headless only).",
)
@click.option(
    "--vault-password",
    default=None,
    help="Vault password — used only when .vault_pass doesn't exist yet (headless only).",
)
@click.option(
    "--path",
    default=None,
    type=click.Path(resolve_path=True),
    help=f"Path to the ansible examples directory (default: {_DEFAULT_EXAMPLES_PATH}).",
)
def main(
    region: str | None,
    api_token: str | None,
    name: str,
    profile: str,
    vault_password: str | None,
    path: str | None,
) -> None:
    """Setup tokens — auto-detects interactive vs headless mode."""
    headless = region is not None or api_token is not None

    if headless:
        if not region or not api_token:
            raise click.UsageError("Headless mode requires both --region and --api-token.")
        _run_headless(
            region=region,
            api_token=api_token,
            name=name,
            profile=profile,
            vault_password=vault_password,
            path=path,
        )
    else:
        try:
            _run_setup(path)
        except (KeyboardInterrupt, click.Abort):
            console.print("\n[dim]Cancelled.[/dim]")


def _run_setup(path: str | None) -> None:
    """Inner setup logic — separated so main() can catch exits cleanly."""
    console.print(
        Panel(
            "[bold]SCCFM Token Setup[/bold]\n"
            "Select or create an API token, then generate\n"
            ".env, vars.yml, and an encrypted vault.yml.",
            border_style="cyan",
        )
    )

    root = _project_root()
    examples_path = _resolve_examples_path(path)
    console.print(f"[dim]Examples directory: {examples_path}[/dim]")

    _verify_ansible_vault()

    # ── Vault password (needed before we can read saved tokens) ──
    vault_pass_path = _ensure_vault_pass(examples_path)

    # ── Token selection ──────────────────────────────────────────
    store = VaultTokenStore(examples_path)
    selected, all_tokens = _select_or_create_token(store)

    region = selected.region
    api_token = selected.token
    token_name = selected.name

    # ── Write files ──────────────────────────────────────────────
    env_path = _write_env_file(root, region, api_token)
    _update_vars_region(examples_path, region)
    vault_path = store.save_active_and_tokens(selected, all_tokens)
    console.print(f"[green]Encrypted vault file updated:[/green] {vault_path}")
    _update_cli_config(region, api_token)

    # ── Summary ──────────────────────────────────────────────────
    summary = Table(title="Setup Complete", show_header=False, border_style="green")
    summary.add_column("Key", style="bold")
    summary.add_column("Value")
    summary.add_row("Token", token_name)
    summary.add_row("Region", region)
    summary.add_row(".env file", str(env_path))
    summary.add_row("Vault file", str(vault_path))
    summary.add_row("Vault password", str(vault_pass_path))
    summary.add_row("CLI config", "~/.sccfm-cli/config.json")

    console.print()
    console.print(summary)
    console.print(
        "\n[green]You can now run playbooks with:[/green]\n"
        "  poetry run ansible-playbook -i examples/inventory.sccfm.yml \\\n"
        "    examples/show_devices.yml --vault-password-file examples/.vault_pass"
    )


if __name__ == "__main__":
    main()

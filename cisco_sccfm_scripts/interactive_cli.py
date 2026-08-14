#!/usr/bin/env python3

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Interactive entry point for SCCFM CLI and development workflows.

Usage:
    sccfm-cli-interactive
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Callable

import click
import questionary
from rich.console import Console
from rich.panel import Panel

console = Console()


# ── Helpers ──────────────────────────────────────────────────────


def _project_root() -> Path:
    """Return the repository root (parent of cisco_sccfm_scripts/)."""
    return Path(__file__).resolve().parent.parent


def _ask(
    choices: list[questionary.Choice | str],
    message: str,
) -> str | None:
    """Searchable select prompt — type to filter, arrow keys to navigate."""
    answer: object = questionary.select(
        message,
        choices=choices,
        use_search_filter=True,
        use_jk_keys=False,
    ).unsafe_ask()
    return answer if isinstance(answer, str) else None


# ── Task implementations ─────────────────────────────────────────


def _configure_profile() -> None:
    """Create or replace a profile in the canonical SCCFM config store."""
    from cisco_sccfm_cli.models import Config
    from cisco_sccfm_cli.services import ConfigService
    from cisco_sccfm_core.constants import SCCFM_REGIONS

    profile_answer = questionary.text("Profile name:", default="default").unsafe_ask()
    profile = (profile_answer or "").strip()
    if not profile:
        console.print("[red]Profile name cannot be empty.[/red]")
        return

    region_answer = questionary.select(
        "SCCFM region:",
        choices=list(SCCFM_REGIONS),
        default="us",
    ).unsafe_ask()
    region = region_answer if isinstance(region_answer, str) else ""
    if not region:
        console.print("[dim]Cancelled.[/dim]")
        return

    token_answer = questionary.password("SCCFM API token:").unsafe_ask()
    api_token = (token_answer or "").strip()
    if not api_token:
        console.print("[red]API token cannot be empty.[/red]")
        return

    ConfigService().save(Config(profile=profile, region=region, api_token=api_token))
    console.print(f"[green]Profile '{profile}' configured for region '{region}'.[/green]")


def _import_legacy_vault() -> None:
    """Import SCCFM profiles from the former Ansible Vault token store."""
    from cisco_sccfm_scripts.import_legacy_vault import main as _import

    _import(standalone_mode=False)


def _run_build_collection() -> None:
    """Build the cisco.sccfm Ansible collection tarball."""
    from cisco_sccfm_scripts.build_ansible_collection import main as _build

    rc = _build()
    if rc:
        console.print(f"[red]Build failed with exit code {rc}[/red]")


def _run_generate_ansible_docs() -> None:
    """Generate Ansible documentation from ansible-doc metadata."""
    from cisco_sccfm_scripts.generate_ansible_docs import main as _generate_ansible_docs

    rc = _generate_ansible_docs([])
    if rc:
        console.print(f"[red]Ansible docs generation failed with exit code {rc}[/red]")


def _run_generate_cli_docs() -> None:
    """Generate CLI documentation from Click help output."""
    from cisco_sccfm_scripts.generate_cli_docs import main as _generate_cli_docs

    rc = _generate_cli_docs([])
    if rc:
        console.print(f"[red]CLI docs generation failed with exit code {rc}[/red]")


def _run_generate_cli_man_docs() -> None:
    """Generate CLI manual pages from Click metadata."""
    from cisco_sccfm_scripts.generate_cli_man_docs import main as _generate_cli_man_docs

    rc = _generate_cli_man_docs([])
    if rc:
        console.print(f"[red]CLI man page generation failed with exit code {rc}[/red]")


def _run_install_cli_man_docs() -> None:
    """Install generated CLI manual pages into the user's man path."""
    from cisco_sccfm_scripts.install_cli_man_docs import main as _install_cli_man_docs

    rc = _install_cli_man_docs([])
    if rc:
        console.print(f"[red]CLI man page installation failed with exit code {rc}[/red]")


def _run_setup_env() -> None:
    """Run the environment bootstrap (pyenv, venv, Poetry deps)."""
    root = _project_root()
    script = root / "cisco_sccfm_scripts" / "setup_environment.sh"
    if not script.exists():
        console.print(f"[red]Script not found: {script}[/red]")
        return
    console.print(f"[dim]Running {script}[/dim]")
    subprocess.call(["bash", str(script)])

    activate = root / "cisco_sccfm_scripts" / "activate.sh"
    if activate.exists():
        console.print(f"[dim]Sourcing {activate}[/dim]")
        subprocess.call(["bash", "-c", f"source {activate}"])
        console.print("[green]Environment activated.[/green]")


def _run_lint() -> None:
    """Run lint with fix (black, isort, mypy)."""
    root = _project_root()
    console.print("[bold]Running black …[/bold]")
    subprocess.call([sys.executable, "-m", "black", "."], cwd=root)
    console.print("[bold]Running isort …[/bold]")
    subprocess.call([sys.executable, "-m", "isort", "."], cwd=root)
    console.print("[bold]Running mypy…[/bold]")
    subprocess.call([sys.executable, "-m", "mypy", "cisco_sccfm_cli", "cisco_sccfm_core"], cwd=root)


def _run_format() -> None:
    """Auto-format code with black and isort."""
    root = _project_root()
    console.print("[bold]Running isort…[/bold]")
    subprocess.call([sys.executable, "-m", "isort", "."], cwd=root)
    console.print("[bold]Running black…[/bold]")
    subprocess.call([sys.executable, "-m", "black", "."], cwd=root)


def _run_test() -> None:
    """Run the test suite with pytest."""
    verbose = questionary.confirm("Verbose output?", default=False).unsafe_ask()

    expression: str | None = questionary.text(
        "Filter expression (-k)? Leave blank for all tests:",
    ).unsafe_ask()

    cmd: list[str] = [sys.executable, "-m", "pytest"]
    if verbose:
        cmd.append("-v")
    normalized_expression = (expression or "").strip()
    if normalized_expression:
        cmd.extend(["-k", normalized_expression])

    subprocess.call(cmd, cwd=_project_root())


def _run_e2e() -> None:
    """Run Ansible e2e integration tests against a real SCCFM tenant."""
    root = _project_root()
    script = root / "sccfm-ansible" / "e2e" / "run_e2e.sh"
    if not script.exists():
        console.print(f"[red]Script not found: {script}[/red]")
        return
    console.print("[bold]Running Ansible e2e integration tests…[/bold]")
    subprocess.call(["bash", str(script)], cwd=root)


# ── Run CLI commands ──────────────────────────────────────────────


def _execute_cli_command(cmd: object) -> None:
    """Prompt for params and run an sccfm-cli leaf command."""
    from cisco_sccfm_scripts.cli_commands import CliCommand, CliParam

    if not isinstance(cmd, CliCommand):
        return
    argv: list[str] = ["sccfm-cli", *cmd.args]
    for param in cmd.params:
        if not isinstance(param, CliParam):
            continue
        if param.is_flag:
            confirmed = questionary.confirm(f"{param.label}?", default=False).unsafe_ask()
            if confirmed:
                argv.append(param.flag)
        elif param.multiple:
            console.print(f"[dim]{param.label} — enter one value per line, blank to finish:[/dim]")
            has_value = False
            while True:
                value: str | None = questionary.text(f"  {param.flag}").unsafe_ask()
                normalized_value = (value or "").strip()
                if not normalized_value:
                    break
                argv.extend([param.flag, normalized_value])
                has_value = True
            if param.required and not has_value:
                console.print(f"[red]{param.label} is required.[/red]")
                return
        else:
            prompt = f"{param.label}{'' if param.required else ' (leave blank to skip)'}"
            single: str | None = questionary.text(prompt).unsafe_ask()
            normalized_value = (single or "").strip()
            if normalized_value:
                argv.extend([param.flag, normalized_value])
            elif param.required:
                console.print(f"[red]{param.label} is required.[/red]")
                return

    console.print(f"[bold cyan]$ {shlex.join(argv)}[/bold cyan]")
    subprocess.call(argv, cwd=_project_root())


def _navigate_cli(children: list[object], title: str) -> None:
    """Recursively navigate a CliGroup/CliCommand tree."""
    from cisco_sccfm_scripts.cli_commands import CliCommand, CliGroup

    nodes: list[CliCommand | CliGroup] = [
        c for c in children if isinstance(c, (CliCommand, CliGroup))
    ]

    while True:
        choices: list[questionary.Choice | str] = [
            questionary.Choice(
                title=f"{n.name:20s} {n.description}",
                value=n.name,
            )
            for n in nodes
        ]
        choices.append(questionary.Choice(title="back", value="back"))

        answer = _ask(choices, f"{title}:")
        if answer is None or answer == "back":
            return

        node = next((n for n in nodes if n.name == answer), None)
        if node is None:
            continue

        if isinstance(node, CliGroup):
            _navigate_cli(node.children, f"{title} > {node.name}")
        elif isinstance(node, CliCommand):
            _execute_cli_command(node)


def _run_cli_commands() -> None:
    """Interactively navigate and run sccfm-cli commands."""
    from cisco_sccfm_scripts.cli_commands import build_cli_tree

    _navigate_cli(build_cli_tree(), "sccfm-cli")


# ── Run Ansible examples ──────────────────────────────────────────


def _run_ansible_examples() -> None:
    """Interactively select and run an Ansible example playbook."""
    examples_dir = _project_root() / "sccfm-ansible" / "examples"
    if not examples_dir.is_dir():
        console.print(f"[red]Examples directory not found: {examples_dir}[/red]")
        return

    playbooks = sorted(
        p.name for p in examples_dir.glob("*.yml") if p.name != "inventory.sccfm.yml"
    )
    if not playbooks:
        console.print("[yellow]No playbooks found in examples directory.[/yellow]")
        return

    answer = _ask([*playbooks, "back"], "Select a playbook:")
    if answer is None or answer == "back":
        return

    if answer not in playbooks:
        console.print("[red]Playbook not found.[/red]")
        return

    cmd = [
        "ansible-playbook",
        answer,
        "-i",
        "inventory.sccfm.yml",
        "--vault-password-file",
        ".vault_pass",
    ]
    console.print(f"[bold cyan]$ {shlex.join(cmd)}[/bold cyan]")
    subprocess.call(cmd, cwd=str(examples_dir))


# ── Manage tokens ─────────────────────────────────────────────────


def _select_profile(message: str) -> object | None:
    """Select a configured SCCFM profile, returning its config."""
    from cisco_sccfm_cli.services import ConfigService

    profiles = ConfigService().list_profiles()
    if not profiles:
        console.print("[yellow]No SCCFM profiles configured.[/yellow]")
        return None

    choices: list[questionary.Choice | str] = [
        questionary.Choice(title=f"{item.profile}  ({item.region})", value=item.profile)
        for item in profiles
    ]
    choices.append("back")
    answer = _ask(choices, message)
    if answer is None or answer == "back":
        return None
    return next((item for item in profiles if item.profile == answer), None)


def _update_profile() -> None:
    """Update the region and API token for an existing profile."""
    from cisco_sccfm_cli.models import Config
    from cisco_sccfm_cli.services import ConfigService
    from cisco_sccfm_core.constants import SCCFM_REGIONS

    selected = _select_profile("Select a profile to update:")
    if not isinstance(selected, Config):
        return

    region_answer = questionary.select(
        "SCCFM region:",
        choices=list(SCCFM_REGIONS),
        default=selected.region,
    ).unsafe_ask()
    region = region_answer if isinstance(region_answer, str) else ""
    if not region:
        console.print("[dim]Cancelled.[/dim]")
        return

    token_answer = questionary.password(
        "New SCCFM API token (leave blank to keep the current token):"
    ).unsafe_ask()
    api_token = (token_answer or "").strip() or selected.api_token
    ConfigService().save(Config(profile=selected.profile, region=region, api_token=api_token))
    console.print(f"[green]Profile '{selected.profile}' updated.[/green]")


def _remove_profile() -> None:
    """Remove an SCCFM profile from the canonical config store."""
    from cisco_sccfm_cli.models import Config
    from cisco_sccfm_cli.services import ConfigService

    selected = _select_profile("Select a profile to remove:")
    if not isinstance(selected, Config):
        return

    confirmed = questionary.confirm(
        f"Remove profile '{selected.profile}' (region={selected.region})?",
        default=False,
    ).unsafe_ask()
    if not confirmed:
        console.print("[dim]Cancelled.[/dim]")
        return

    ConfigService().remove(selected.profile)
    console.print(f"[green]Profile '{selected.profile}' removed.[/green]")


def _manage_profiles() -> None:
    """Profile management sub-menu."""
    answer = _ask(["update", "remove", "back"], "Manage profiles:")
    if answer is None or answer == "back":
        return

    if answer == "update":
        _update_profile()
    elif answer == "remove":
        _remove_profile()


# ── Menu definition ───────────────────────────────────────────────

_TASKS: list[tuple[str, str, Callable[[], None]]] = [
    ("configure-profile", "Create or replace an SCCFM profile", _configure_profile),
    ("manage-profiles", "Update or remove SCCFM profiles", _manage_profiles),
    (
        "import-legacy-vault",
        "Import profiles from the former Ansible Vault token store",
        _import_legacy_vault,
    ),
    ("run-cli", "Run an sccfm-cli command interactively", _run_cli_commands),
    ("run-ansible", "Run an Ansible example playbook", _run_ansible_examples),
    ("build-collection", "Build the cisco.sccfm Ansible collection tarball", _run_build_collection),
    (
        "generate-ansible-docs",
        "Generate Ansible reference docs from ansible-doc output",
        _run_generate_ansible_docs,
    ),
    (
        "generate-cli-docs",
        "Generate CLI reference docs from Click help output",
        _run_generate_cli_docs,
    ),
    (
        "generate-cli-man-docs",
        "Generate CLI man pages from Click metadata",
        _run_generate_cli_man_docs,
    ),
    (
        "install-cli-man-docs",
        "Install generated CLI man pages for local man lookup",
        _run_install_cli_man_docs,
    ),
    ("setup-env", "Bootstrap environment (pyenv, venv, Poetry deps)", _run_setup_env),
    ("test", "Run the test suite (pytest)", _run_test),
    ("run-e2e", "Run Ansible e2e integration tests (real tenant)", _run_e2e),
    ("lint", "Run CI lint checks (black + isort + mypy)", _run_lint),
    ("format", "Auto-format code (black + isort)", _run_format),
]


def _dispatch(answer: str) -> bool:
    """Execute the task by name. Returns False to exit."""
    if answer == "exit":
        return False
    for task_name, _, fn in _TASKS:
        if task_name == answer:
            fn()
            return True
    return True


# ── Interactive loop ──────────────────────────────────────────────


def _interactive_menu() -> None:
    """Show an interactive menu and run the selected task."""
    console.print(
        Panel(
            "[bold]SCCFM CLI Interactive[/bold]\n" "Select a task to run.",
            border_style="cyan",
        )
    )

    choices: list[questionary.Choice | str] = [
        questionary.Choice(
            title=f"{name:20s} {desc}",
            value=name,
        )
        for name, desc, _ in _TASKS
    ]
    choices.append(questionary.Choice(title="exit", value="exit"))
    while True:
        try:
            answer = _ask(choices, "What would you like to do?")
        except KeyboardInterrupt:
            break

        if answer is None:
            break

        console.print()
        try:
            if not _dispatch(answer):
                break
        except KeyboardInterrupt:
            console.print("\n[yellow]Exiting.[/yellow]")
            break
        console.print()

    console.print("[dim]Bye![/dim]")


# ── Entry-point ───────────────────────────────────────────────────


@click.command(help="Open the interactive SCCFM CLI and development workflow menu.")
def main() -> None:
    try:
        _interactive_menu()
    except KeyboardInterrupt:
        console.print("\n[dim]Bye![/dim]")


if __name__ == "__main__":
    main()

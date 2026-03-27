#!/usr/bin/env python3
"""Unified devkit CLI — interactive entry-point for all helper scripts.

Usage:
    poetry run devkit          # interactive menu
    poetry run devkit --help   # show available commands
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Callable

import questionary
from rich.console import Console
from rich.panel import Panel

console = Console()


# ── Helpers ──────────────────────────────────────────────────────


def _project_root() -> Path:
    """Return the repository root (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent


def _ask(
    choices: list[questionary.Choice | str],
    message: str,
) -> str | None:
    """Searchable select prompt — type to filter, arrow keys to navigate."""
    return questionary.select(
        message,
        choices=choices,
        use_search_filter=True,
        use_jk_keys=False,
    ).unsafe_ask()


# ── Task implementations ─────────────────────────────────────────


def _run_change_tokens() -> None:
    """Set up SCCFM API tokens, .env, and Ansible Vault (interactive)."""
    from scripts.setup_tokens import main as _setup_tokens

    _setup_tokens(standalone_mode=False)


def _run_build_collection() -> None:
    """Build the cisco.sccfm Ansible collection tarball."""
    from scripts.build_ansible_collection import main as _build

    rc = _build()
    if rc:
        console.print(f"[red]Build failed with exit code {rc}[/red]")


def _run_setup_env() -> None:
    """Run the environment bootstrap (pyenv, venv, Poetry deps)."""
    root = _project_root()
    script = root / "scripts" / "setup_environment.sh"
    if not script.exists():
        console.print(f"[red]Script not found: {script}[/red]")
        return
    console.print(f"[dim]Running {script}[/dim]")
    subprocess.call(["bash", str(script)])

    activate = root / "scripts" / "activate.sh"
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
    subprocess.call([sys.executable, "-m", "mypy", "sccfm_cli", "sccfm_core"], cwd=root)


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
    if expression.strip():
        cmd.extend(["-k", expression.strip()])

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
    from scripts.cli_commands import CliCommand, CliParam

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
                if not value.strip():
                    break
                argv.extend([param.flag, value.strip()])
                has_value = True
            if param.required and not has_value:
                console.print(f"[red]{param.label} is required.[/red]")
                return
        else:
            prompt = f"{param.label}{'' if param.required else ' (leave blank to skip)'}"
            single: str | None = questionary.text(prompt).unsafe_ask()
            if single.strip():
                argv.extend([param.flag, single.strip()])
            elif param.required:
                console.print(f"[red]{param.label} is required.[/red]")
                return

    console.print(f"[bold cyan]$ {shlex.join(argv)}[/bold cyan]")
    subprocess.call(argv, cwd=_project_root())


def _navigate_cli(children: list[object], title: str) -> None:
    """Recursively navigate a CliGroup/CliCommand tree."""
    from scripts.cli_commands import CliCommand, CliGroup

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
    from scripts.cli_commands import build_cli_tree

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


def _update_token() -> None:
    """Prompt for a new API token for an existing named token."""
    from scripts.setup_tokens import _resolve_examples_path
    from scripts.token_store import SavedToken, VaultTokenStore

    try:
        examples_path = _resolve_examples_path(None)
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        return

    store = VaultTokenStore(examples_path)
    tokens = store.list_tokens()

    if not tokens:
        console.print("[yellow]No saved tokens found in vault.[/yellow]")
        return

    token_choices: list[questionary.Choice | str] = [
        questionary.Choice(
            title=f"{t.name}  ({t.region})  …{t.token[-6:]}",
            value=t.name,
        )
        for t in tokens
    ]
    token_choices.append("back")

    answer = _ask(token_choices, "Select a token to update:")
    if answer is None or answer == "back":
        return

    token_to_update = next((t for t in tokens if t.name == answer), None)
    if token_to_update is None:
        console.print("[red]Token not found.[/red]")
        return

    new_token_value = questionary.text(
        f"Paste new API token for '{token_to_update.name}':",
    ).unsafe_ask()
    new_token_value = new_token_value.strip()
    if not new_token_value:
        console.print("[red]Token cannot be empty.[/red]")
        return

    updated = SavedToken(
        name=token_to_update.name,
        region=token_to_update.region,
        token=new_token_value,
    )
    all_tokens = [updated if t.name == updated.name else t for t in tokens]
    vault_path = store.save_active_and_tokens(updated, all_tokens)
    console.print(f"[green]Updated token '{updated.name}'.[/green]")
    console.print(f"[dim]Vault updated: {vault_path}[/dim]")


def _remove_token() -> None:
    """Remove a saved token from the Ansible vault store."""
    from scripts.setup_tokens import _resolve_examples_path
    from scripts.token_store import VaultTokenStore

    try:
        examples_path = _resolve_examples_path(None)
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        return

    store = VaultTokenStore(examples_path)
    tokens = store.list_tokens()

    if not tokens:
        console.print("[yellow]No saved tokens found in vault.[/yellow]")
        return

    if len(tokens) == 1:
        console.print("[yellow]Only one token saved — cannot remove the last token.[/yellow]")
        return

    # Use Choice so the display shows region/token context but the value is just the name.
    token_choices: list[questionary.Choice | str] = [
        questionary.Choice(
            title=f"{t.name}  ({t.region})  …{t.token[-6:]}",
            value=t.name,
        )
        for t in tokens
    ]
    token_choices.append("back")

    answer = _ask(token_choices, "Select a token to remove:")
    if answer is None or answer == "back":
        return

    token_to_remove = next((t for t in tokens if t.name == answer), None)
    if token_to_remove is None:
        console.print("[red]Token not found.[/red]")
        return

    confirmed = questionary.confirm(
        f"Remove token '{token_to_remove.name}' (region={token_to_remove.region})?",
        default=True,
    ).unsafe_ask()
    if not confirmed:
        console.print("[dim]Cancelled.[/dim]")
        return

    remaining = [t for t in tokens if t.name != token_to_remove.name]
    new_active = remaining[0]
    vault_path = store.save_active_and_tokens(new_active, remaining)
    console.print(f"[green]Removed token '{token_to_remove.name}'.[/green]")
    console.print(
        f"[green]Active token is now '{new_active.name}' (region={new_active.region}).[/green]"
    )
    console.print(f"[dim]Vault updated: {vault_path}[/dim]")


def _manage_tokens() -> None:
    """Token management sub-menu (update or remove)."""
    answer = _ask(["update", "remove", "back"], "Manage tokens:")
    if answer is None or answer == "back":
        return

    if answer == "update":
        _update_token()
    elif answer == "remove":
        _remove_token()


# ── Menu definition ───────────────────────────────────────────────

_TASKS: list[tuple[str, str, Callable[[], None]]] = [
    ("change-tokens", "Set up SCCFM API tokens, .env, and Ansible Vault", _run_change_tokens),
    ("manage-tokens", "Manage saved tokens (update / remove)", _manage_tokens),
    ("run-cli", "Run an sccfm-cli command interactively", _run_cli_commands),
    ("run-ansible", "Run an Ansible example playbook", _run_ansible_examples),
    ("build-collection", "Build the cisco.sccfm Ansible collection tarball", _run_build_collection),
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
            "[bold]SCCFM Developer Toolkit[/bold]\n" "Select a task to run.",
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


def main() -> None:
    try:
        _interactive_menu()
    except KeyboardInterrupt:
        console.print("\n[dim]Bye![/dim]")


if __name__ == "__main__":
    main()

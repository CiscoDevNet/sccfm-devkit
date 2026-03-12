#!/usr/bin/env python3
"""Unified devkit CLI — interactive entry-point for all helper scripts.

Usage:
    poetry run devkit          # interactive menu
    poetry run devkit --help   # show available commands
"""

from __future__ import annotations

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


# ── Task implementations ─────────────────────────────────────────


def _run_setup_tokens() -> None:
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
    """Run linters (mypy, flake8) on the project."""
    root = _project_root()
    console.print("[bold]Running mypy…[/bold]")
    subprocess.call([sys.executable, "-m", "mypy", "sccfm_cli", "sccfm_core"], cwd=root)
    console.print("[bold]Running flake8…[/bold]")
    subprocess.call(
        [sys.executable, "-m", "flake8", "sccfm_cli", "sccfm_core", "scripts"],
        cwd=root,
    )


def _run_format() -> None:
    """Auto-format code with black and isort."""
    root = _project_root()
    console.print("[bold]Running isort…[/bold]")
    subprocess.call([sys.executable, "-m", "isort", "."], cwd=root)
    console.print("[bold]Running black…[/bold]")
    subprocess.call([sys.executable, "-m", "black", "."], cwd=root)


def _run_test() -> None:
    """Run the test suite with pytest."""
    verbose = questionary.confirm("Verbose output?", default=False).ask()
    if verbose is None:
        return  # user cancelled

    expression: str | None = questionary.text(
        "Filter expression (-k)? Leave blank for all tests:",
    ).ask()
    if expression is None:
        return

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
    console.print("[bold]Running Ansible e2e integration tests\u2026[/bold]")
    subprocess.call(["bash", str(script)], cwd=root)


# ── Menu definition ──────────────────────────────────────────────

_TASKS: list[tuple[str, str, Callable[[], None]]] = [
    ("setup-tokens", "Set up SCCFM API tokens, .env, and Ansible Vault", _run_setup_tokens),
    ("build-collection", "Build the cisco.sccfm Ansible collection tarball", _run_build_collection),
    ("setup-env", "Bootstrap environment (pyenv, venv, Poetry deps)", _run_setup_env),
    ("test", "Run the test suite (pytest)", _run_test),
    ("run-e2e", "Run Ansible e2e integration tests (real tenant)", _run_e2e),
    ("lint", "Run linters (mypy + flake8)", _run_lint),
    ("format", "Auto-format code (black + isort)", _run_format),
]


def _build_choices() -> list[questionary.Choice]:
    """Build the questionary choice list from registered tasks."""
    return [questionary.Choice(title=f"{name:<20} {desc}", value=name) for name, desc, _ in _TASKS]


def _dispatch(name: str) -> None:
    """Look up and execute a task by name."""
    for task_name, _, fn in _TASKS:
        if task_name == name:
            fn()
            return
    console.print(f"[red]Unknown task: {name}[/red]")


# ── Interactive loop ─────────────────────────────────────────────


def _interactive_menu() -> None:
    """Show an interactive menu and run the selected task."""
    console.print(
        Panel(
            "[bold]SCCFM Developer Toolkit[/bold]\n" "Select a task to run.",
            border_style="cyan",
        )
    )

    while True:
        try:
            answer: str | None = questionary.select(
                "What would you like to do?",
                choices=[*_build_choices(), questionary.Choice(title="Exit", value="_exit")],
            ).ask()
        except KeyboardInterrupt:
            break

        if answer is None or answer == "_exit":
            break

        console.print()
        try:
            _dispatch(answer)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
        console.print()

    console.print("[dim]Bye![/dim]")


# ── Entry-point ──────────────────────────────────────────────────


def main() -> None:
    try:
        _interactive_menu()
    except KeyboardInterrupt:
        console.print("\n[dim]Bye![/dim]")


if __name__ == "__main__":
    main()

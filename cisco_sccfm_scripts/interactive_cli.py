#!/usr/bin/env python3

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Interactive entry point for SCCFM repository development workflows.

Usage:
    sccfm-devkit
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Mapping, Sequence

import click
import questionary
from rich.console import Console
from rich.panel import Panel

from cisco_sccfm_cli.interactive import customer_tasks

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


def _require_success(action: str, return_code: int) -> None:
    """Raise a user-facing error when an in-process development task fails."""
    if return_code:
        raise click.ClickException(f"{action} failed with exit code {return_code}")


def _run_checked(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
) -> None:
    """Run a child command and propagate its nonzero status to the menu."""
    return_code = subprocess.call(
        list(command),
        cwd=cwd,
        env=dict(env) if env is not None else None,
    )
    if return_code:
        raise click.ClickException(
            f"Command failed with exit code {return_code}: {shlex.join(command)}"
        )


@contextmanager
def _source_collection_environment(project_root: Path) -> Iterator[dict[str, str]]:
    """Expose the source collection through a valid Ansible collection root."""
    collection_dir = project_root / "sccfm-ansible"
    with tempfile.TemporaryDirectory(prefix="sccfm-collection-") as temporary_directory:
        collection_root = Path(temporary_directory)
        namespace_dir = collection_root / "ansible_collections" / "cisco"
        namespace_dir.mkdir(parents=True)
        (namespace_dir / "sccfm").symlink_to(collection_dir, target_is_directory=True)

        env = os.environ.copy()
        existing_paths = env.get("ANSIBLE_COLLECTIONS_PATH")
        paths = [str(collection_root)]
        if existing_paths:
            paths.append(existing_paths)
        env["ANSIBLE_COLLECTIONS_PATH"] = os.pathsep.join(paths)
        yield env


# ── Task implementations ─────────────────────────────────────────


def _import_legacy_vault() -> None:
    """Import SCCFM profiles from the former Ansible Vault token store."""
    from cisco_sccfm_scripts.import_legacy_vault import main as _import

    _import(standalone_mode=False)


def _run_build_collection() -> None:
    """Build the cisco.sccfm Ansible collection tarball."""
    from cisco_sccfm_scripts.build_ansible_collection import main as _build

    _require_success("Collection build", _build([]))


def _run_generate_ansible_docs() -> None:
    """Generate Ansible documentation from ansible-doc metadata."""
    from cisco_sccfm_scripts.generate_ansible_docs import main as _generate_ansible_docs

    _require_success("Ansible docs generation", _generate_ansible_docs([]))


def _run_generate_cli_docs() -> None:
    """Generate CLI documentation from Click help output."""
    from cisco_sccfm_scripts.generate_cli_docs import main as _generate_cli_docs

    _require_success("CLI docs generation", _generate_cli_docs([]))


def _run_generate_cli_man_docs() -> None:
    """Generate CLI manual pages from Click metadata."""
    from cisco_sccfm_scripts.generate_cli_man_docs import main as _generate_cli_man_docs

    _require_success("CLI man page generation", _generate_cli_man_docs([]))


def _run_install_cli_man_docs() -> None:
    """Install generated CLI manual pages into the user's man path."""
    from cisco_sccfm_scripts.install_cli_man_docs import main as _install_cli_man_docs

    _require_success("CLI man page installation", _install_cli_man_docs([]))


def _run_setup_env() -> None:
    """Run the environment bootstrap (pyenv, venv, Poetry deps)."""
    root = _project_root()
    script = root / "cisco_sccfm_scripts" / "setup_environment.sh"
    if not script.exists():
        console.print(f"[red]Script not found: {script}[/red]")
        return
    console.print(f"[dim]Running {script}[/dim]")
    _run_checked(["bash", str(script)], cwd=root)

    activate = root / "cisco_sccfm_scripts" / "activate.sh"
    if activate.exists():
        console.print(f"[green]Setup complete. Run 'source {activate}' in your shell.[/green]")


def _run_lint() -> None:
    """Run read-only formatting and type checks."""
    root = _project_root()
    console.print("[bold]Running black …[/bold]")
    _run_checked([sys.executable, "-m", "black", "--check", "."], cwd=root)
    console.print("[bold]Running isort …[/bold]")
    _run_checked([sys.executable, "-m", "isort", "--check-only", "."], cwd=root)
    console.print("[bold]Running mypy…[/bold]")
    _run_checked(
        [sys.executable, "-m", "mypy", "cisco_sccfm_cli", "cisco_sccfm_core"],
        cwd=root,
    )


def _run_format() -> None:
    """Auto-format code with black and isort."""
    root = _project_root()
    console.print("[bold]Running isort…[/bold]")
    _run_checked([sys.executable, "-m", "isort", "."], cwd=root)
    console.print("[bold]Running black…[/bold]")
    _run_checked([sys.executable, "-m", "black", "."], cwd=root)


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

    _run_checked(cmd, cwd=_project_root())


def _run_e2e() -> None:
    """Run Ansible e2e integration tests against a real SCCFM tenant."""
    root = _project_root()
    script = root / "sccfm-ansible" / "e2e" / "run_e2e.sh"
    if not script.exists():
        console.print(f"[red]Script not found: {script}[/red]")
        return
    console.print("[bold]Running Ansible e2e integration tests…[/bold]")
    _run_checked(["bash", str(script)], cwd=root)


# ── Run Ansible examples ──────────────────────────────────────────


def _playbook_requires_vault(playbook: Path) -> bool:
    """Return whether *playbook* references vault variables outside comments."""
    try:
        content = playbook.read_text(encoding="utf-8")
    except OSError:
        return False
    return any(
        "vault_" in line for line in content.splitlines() if not line.lstrip().startswith("#")
    )


def _vault_password_arguments(examples_dir: Path, playbook: Path) -> list[str]:
    """Return Vault arguments required by the selected example workspace."""
    vault_file = examples_dir / "group_vars" / "all" / "vault.yml"
    vault_password_file = examples_dir / ".vault_pass"
    playbook_uses_vault = _playbook_requires_vault(playbook)

    if not vault_file.exists() and not playbook_uses_vault:
        return []
    if not vault_file.is_file():
        raise click.ClickException(
            f"{playbook.name} uses Vault variables but {vault_file} was not found. "
            "Create and encrypt it as described in sccfm-ansible/README.md."
        )
    if not vault_password_file.is_file():
        raise click.ClickException(
            f"{vault_file} is present, but {vault_password_file} was not found. "
            "Create the password file before running Ansible examples."
        )
    return ["--vault-password-file", vault_password_file.name]


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
    ]
    cmd.extend(_vault_password_arguments(examples_dir, examples_dir / answer))
    console.print(f"[bold cyan]$ {shlex.join(cmd)}[/bold cyan]")
    with _source_collection_environment(_project_root()) as env:
        _run_checked(cmd, cwd=examples_dir, env=env)


# ── Menu definition ───────────────────────────────────────────────

Task = tuple[str, str, Callable[[], None]]


def _customer_task_entries() -> list[Task]:
    """Return public customer tasks in the development menu's tuple format."""
    return [(task.name, task.description, task.action) for task in customer_tasks()]


_TASKS: list[Task] = [
    *_customer_task_entries(),
    (
        "import-legacy-vault",
        "Import profiles from the former Ansible Vault token store",
        _import_legacy_vault,
    ),
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
            "[bold]SCCFM DevKit[/bold]\n" "Select a task to run.",
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


@click.command(help="Open the SCCFM repository development workflow menu.")
def main() -> None:
    try:
        _interactive_menu()
    except KeyboardInterrupt:
        console.print("\n[dim]Bye![/dim]")


if __name__ == "__main__":
    main()

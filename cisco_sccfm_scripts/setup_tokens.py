#!/usr/bin/env python3

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Setup for SCCFM API tokens, .env, and Ansible Vault.

Runs **interactively** by default (prompts for region, token, etc.).
Supply ``--region`` with ``SCCFM_API_TOKEN`` to run **headless** — suitable
for CI pipelines and scripted workflows. When a private ``.vault_pass`` does
not exist yet, supply ``SCCFM_VAULT_PASSWORD`` as well. The legacy
``--api-token`` and ``--vault-password`` options remain available but can expose
secrets in shell history and process listings.

Manages a local token store so tokens can be reused across setups. Existing
vaults with the legacy ``sccfm_api_token`` field are migrated on the next save.
Creates / updates:
  - .env              (SCCFM_REGION, SCCFM_API_TOKEN)
  - .vault_pass       (vault password file)
  - group_vars/all/vars.yml   (sccfm_region)
  - group_vars/all/vault.yml  (encrypted vault_sccfm_api_token)
  - ~/.sccfm-cli/config.json  (CLI profile)

Examples::

    # Interactive (default)
    python cisco_sccfm_scripts/setup_tokens.py

    # Headless — secrets are injected by the CI environment
    python cisco_sccfm_scripts/setup_tokens.py --region us

    # Headless — optional non-secret settings
    python cisco_sccfm_scripts/setup_tokens.py \\
        --region int --name staging --profile staging
"""

from __future__ import annotations

import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from errno import ELOOP, ENOTDIR
from pathlib import Path
from typing import Iterator

import click
import questionary
from click.core import ParameterSource
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cisco_sccfm_core.constants import SCCFM_REGIONS
from cisco_sccfm_scripts.token_store import (
    ActiveTokenRegionRequired,
    SavedToken,
    VaultTokenStore,
    validate_user_token_name,
)

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


@dataclass(frozen=True)
class _FileSnapshot:
    """Recoverable state for one coordinated credential file."""

    path: Path
    content: bytes | None = field(repr=False)
    mode: int | None


@dataclass(frozen=True)
class _PosixFileSnapshot:
    """Recoverable state anchored to an already-open parent directory."""

    path: Path
    parent_descriptor: int = field(repr=False)
    name: str
    content: bytes | None = field(repr=False)
    mode: int | None


class _PosixCredentialTransaction:
    """Descriptor-anchored credential snapshot and I/O boundary."""

    def __init__(self, snapshots: list[_PosixFileSnapshot]) -> None:
        self._snapshots = snapshots
        self._by_path = {snapshot.path: snapshot for snapshot in snapshots}

    def _snapshot(self, path: Path) -> _PosixFileSnapshot | None:
        normalized = _platform_normalized_path(path)
        return self._by_path.get(normalized)

    def manages(self, path: Path) -> bool:
        return self._snapshot(path) is not None

    def read_bytes(self, path: Path) -> bytes | None:
        snapshot = self._snapshot(path)
        if snapshot is None:
            return None
        captured = _read_regular_relative(path, snapshot.parent_descriptor)
        return None if captured is None else captured[0]

    def write_bytes(self, path: Path, content: bytes, *, mode: int) -> bool:
        snapshot = self._snapshot(path)
        if snapshot is None:
            return False
        _write_relative_bytes(snapshot, content, mode=mode)
        return True

    def parent_descriptor(self, path: Path) -> int | None:
        snapshot = self._snapshot(path)
        return None if snapshot is None else snapshot.parent_descriptor


_active_credential_transaction: _PosixCredentialTransaction | None = None


def _project_root() -> Path:
    """Return the repository root (parent of cisco_sccfm_scripts/)."""
    return Path(__file__).resolve().parent.parent


# ── Path resolution ──────────────────────────────────────────────


def _resolve_examples_path(path: str | Path | None) -> Path:
    """Return the absolute examples directory, raising if it cannot be found."""
    if path is not None:
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_dir():
            raise click.ClickException(f"Directory not found: {resolved}")
        if not os.access(resolved, os.W_OK):
            raise click.ClickException(f"Examples directory is not writable: {resolved}")
        return resolved

    default = Path.cwd() / _DEFAULT_EXAMPLES_PATH
    if default.is_dir():
        return default.resolve()

    cwd = Path.cwd()
    if (cwd / "group_vars").is_dir() and (cwd / ".vault_pass.example").exists():
        return cwd.resolve()

    raise click.ClickException(
        "Could not locate the ansible examples directory.\n"
        "Run from the project root or pass --path explicitly."
    )


def _write_private_text(path: Path, content: str) -> None:
    """Atomically write UTF-8 text with mode 0600."""
    _write_bytes(path, content.encode("utf-8"), mode=0o600)


def _write_bytes(path: Path, content: bytes, *, mode: int) -> None:
    """Atomically write bytes at an explicit mode without following a final symlink."""
    if _active_credential_transaction is not None and _active_credential_transaction.write_bytes(
        path, content, mode=mode
    ):
        return
    _validate_path_ancestors(path)
    if path.parent.is_symlink():
        raise click.ClickException(
            f"Refusing to write through a symlinked directory: {path.parent}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        path.chmod(mode)
    finally:
        temporary_path.unlink(missing_ok=True)


def _capture_file(path: Path) -> _FileSnapshot:
    """Capture a regular file before a coordinated credential update."""
    _validate_path_ancestors(path)
    if path.is_symlink():
        raise click.ClickException(f"Refusing to snapshot a symlinked credential file: {path}")
    if not path.exists():
        return _FileSnapshot(path=path, content=None, mode=None)
    if not path.is_file():
        raise click.ClickException(f"Credential path is not a regular file: {path}")
    return _FileSnapshot(
        path=path,
        content=path.read_bytes(),
        mode=stat.S_IMODE(path.stat().st_mode),
    )


def _restore_file(snapshot: _FileSnapshot) -> None:
    """Restore one credential snapshot after a failed coordinated update."""
    if snapshot.content is None:
        if snapshot.path.is_symlink():
            raise RuntimeError("credential rollback encountered a symlink")
        snapshot.path.unlink(missing_ok=True)
        return
    _write_bytes(
        snapshot.path,
        snapshot.content,
        mode=snapshot.mode or 0o600,
    )


def _safe_open_flags() -> int:
    """Return flags that refuse symlinks and blocking special files."""
    return getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)


def _credential_path_changed(path: Path) -> click.ClickException:
    return click.ClickException(f"Credential path changed or contains a symbolic link: {path}")


def _open_posix_parent(path: Path) -> int:
    """Open every existing ancestor without following symlinks.

    Missing suffix components are created descriptor-relatively. Holding the
    returned descriptor pins the parent used for the whole transaction, so a
    later pathname swap cannot redirect either snapshot or rollback.
    """
    parent = path.parent
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | _safe_open_flags()
    descriptor = os.open(parent.anchor, flags)
    try:
        for component in parent.parts[1:]:
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                try:
                    os.mkdir(component, mode=stat.S_IRWXU, dir_fd=descriptor)
                except FileExistsError:
                    pass
                child = os.open(component, flags, dir_fd=descriptor)
            except OSError as exc:
                if exc.errno in (ELOOP, ENOTDIR):
                    raise _credential_path_changed(path) from exc
                raise
            try:
                child_stat = os.fstat(child)
                entry_stat = os.stat(
                    component,
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
                if (
                    not stat.S_ISDIR(child_stat.st_mode)
                    or stat.S_ISLNK(entry_stat.st_mode)
                    or not os.path.samestat(child_stat, entry_stat)
                ):
                    raise _credential_path_changed(path)
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _read_regular_relative(path: Path, parent_descriptor: int) -> tuple[bytes, int] | None:
    """Read one credential file relative to a pinned parent directory."""
    flags = os.O_RDONLY | _safe_open_flags()
    try:
        descriptor = os.open(path.name, flags, dir_fd=parent_descriptor)
    except FileNotFoundError:
        return None
    except OSError as exc:
        if exc.errno in (ELOOP, ENOTDIR):
            raise _credential_path_changed(path) from exc
        raise
    try:
        descriptor_stat = os.fstat(descriptor)
        entry_stat = os.stat(
            path.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(descriptor_stat.st_mode)
            or stat.S_ISLNK(entry_stat.st_mode)
            or not os.path.samestat(descriptor_stat, entry_stat)
        ):
            raise _credential_path_changed(path)
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks), stat.S_IMODE(descriptor_stat.st_mode)
    finally:
        os.close(descriptor)


def _capture_posix_file(path: Path) -> _PosixFileSnapshot:
    """Capture a credential file through a pinned, descriptor-walked parent."""
    parent_descriptor = _open_posix_parent(path)
    try:
        captured = _read_regular_relative(path, parent_descriptor)
        if captured is None:
            return _PosixFileSnapshot(path, parent_descriptor, path.name, None, None)
        content, mode = captured
        return _PosixFileSnapshot(path, parent_descriptor, path.name, content, mode)
    except BaseException:
        os.close(parent_descriptor)
        raise


def _restore_posix_file(snapshot: _PosixFileSnapshot) -> None:
    """Restore through the parent descriptor captured before the update."""
    if snapshot.content is None:
        try:
            entry_stat = os.stat(
                snapshot.name,
                dir_fd=snapshot.parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return
        if stat.S_ISLNK(entry_stat.st_mode) or not stat.S_ISREG(entry_stat.st_mode):
            raise RuntimeError("credential rollback encountered an unsafe path")
        os.unlink(snapshot.name, dir_fd=snapshot.parent_descriptor)
        return

    _write_relative_bytes(snapshot, snapshot.content, mode=snapshot.mode or 0o600)


def _write_relative_bytes(
    snapshot: _PosixFileSnapshot,
    content: bytes,
    *,
    mode: int,
) -> None:
    """Atomically replace one file relative to its pinned parent descriptor."""
    temporary_name = f".{snapshot.name}.update-{os.getpid()}-{id(content):x}"
    descriptor = os.open(
        temporary_name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | _safe_open_flags(),
        mode,
        dir_fd=snapshot.parent_descriptor,
    )
    try:
        os.fchmod(descriptor, mode)
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
        os.replace(
            temporary_name,
            snapshot.name,
            src_dir_fd=snapshot.parent_descriptor,
            dst_dir_fd=snapshot.parent_descriptor,
        )
    finally:
        os.close(descriptor)
        try:
            os.unlink(temporary_name, dir_fd=snapshot.parent_descriptor)
        except FileNotFoundError:
            pass


def _close_posix_snapshots(snapshots: list[_PosixFileSnapshot]) -> None:
    for snapshot in snapshots:
        os.close(snapshot.parent_descriptor)


def _capture_posix_files(paths: list[Path]) -> list[_PosixFileSnapshot]:
    """Capture all files, closing already-open parents if preflight fails."""
    snapshots: list[_PosixFileSnapshot] = []
    try:
        for path in paths:
            snapshots.append(_capture_posix_file(path))
        return snapshots
    except BaseException:
        _close_posix_snapshots(snapshots)
        raise


def _platform_normalized_path(path: Path) -> Path:
    """Normalize only macOS's fixed root aliases, never user-controlled links."""
    absolute = path.expanduser().absolute()
    if sys.platform == "darwin" and absolute.parts[:2] == ("/", "var"):
        return Path("/private").joinpath(*absolute.parts[1:])
    return absolute


def _read_transaction_text(path: Path) -> str | None:
    """Read UTF-8 content through the active transaction when managed by it."""
    if _active_credential_transaction is None:
        return None
    content = _active_credential_transaction.read_bytes(path)
    return None if content is None else content.decode("utf-8")


def _transaction_manages(path: Path) -> bool:
    return _active_credential_transaction is not None and _active_credential_transaction.manages(
        path
    )


def _validate_path_ancestors(path: Path) -> None:
    """Reject symlinked or non-directory ancestors of a credential path."""
    absolute = path.expanduser().absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:-1]:
        current /= part
        if current.is_symlink():
            raise click.ClickException(
                f"Refusing to use a credential path through symlinked directory: {current}"
            )
        if current.exists() and not current.is_dir():
            raise click.ClickException(f"Credential path ancestor is not a directory: {current}")


@contextmanager
def _credential_transaction(paths: list[Path]) -> Iterator[None]:
    """Roll back every listed credential file if a coordinated update fails."""
    global _active_credential_transaction

    unique_paths = list(dict.fromkeys(_platform_normalized_path(path) for path in paths))
    if _active_credential_transaction is not None:
        raise RuntimeError("Nested credential transactions are not supported")
    if os.name != "posix":
        snapshots = [_capture_file(path) for path in unique_paths]
        try:
            yield
        except BaseException:
            rollback_failed = False
            for file_snapshot in reversed(snapshots):
                try:
                    _restore_file(file_snapshot)
                except (OSError, RuntimeError, click.ClickException):
                    rollback_failed = True
            if rollback_failed:
                raise RuntimeError(
                    "Credential update failed and its previous state could not be fully restored"
                ) from None
            raise
        return

    posix_snapshots: list[_PosixFileSnapshot] = []
    try:
        posix_snapshots = _capture_posix_files(unique_paths)
        _active_credential_transaction = _PosixCredentialTransaction(posix_snapshots)
        try:
            yield
        except BaseException:
            rollback_failed = False
            for posix_snapshot in reversed(posix_snapshots):
                try:
                    _restore_posix_file(posix_snapshot)
                except (OSError, RuntimeError, click.ClickException):
                    rollback_failed = True
            if rollback_failed:
                raise RuntimeError(
                    "Credential update failed and its previous state could not be fully restored"
                ) from None
            raise
    finally:
        _active_credential_transaction = None
        _close_posix_snapshots(posix_snapshots)


def _credential_state_paths(root: Path, examples_path: Path) -> list[Path]:
    """Return every file updated when the active credential changes."""
    return [
        root / ".env",
        examples_path / "group_vars" / "all" / "vars.yml",
        examples_path / "group_vars" / "all" / "vault.yml",
        _resolved_config_path(),
    ]


def _credential_transaction_paths(root: Path, examples_path: Path) -> list[Path]:
    """Include the read-only Vault password input in transaction preflight."""
    return [*_credential_state_paths(root, examples_path), examples_path / ".vault_pass"]


def _resolved_config_path() -> Path:
    """Return the same CLI config path selected by SCCFM_CONFIG/ConfigService."""
    config_value = os.environ.get("SCCFM_CONFIG")
    return (
        Path(config_value).expanduser()
        if config_value
        else Path.home() / ".sccfm-cli" / "config.json"
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
            title=f"{t.name:<20} region={t.region}",
            value=f"token:{index}",
        )
        for index, t in enumerate(saved)
    ]
    choices.append(questionary.Choice(title="+ Add a new token", value="action:new"))

    answer: str | None = questionary.select(
        "Select a saved token or add a new one:",
        choices=choices,
    ).ask()

    if answer is None:
        raise click.Abort()

    if answer == "action:new":
        new_token = _prompt_new_token()
        if any(token.name != new_token.name and token.token == new_token.token for token in saved):
            raise click.ClickException("That API token is already saved under a different name.")
        all_tokens = [t for t in saved if t.name != new_token.name]
        all_tokens.append(new_token)
        return new_token, all_tokens

    try:
        selected = saved[int(answer.removeprefix("token:"))]
    except (ValueError, IndexError):
        raise click.ClickException("Selected token was not found in the Vault.") from None
    return selected, saved


def _prompt_new_token() -> SavedToken:
    """Interactively gather a new token."""
    region = _prompt_region()
    api_token = _prompt_token()
    name = _prompt_token_name()
    return _saved_token(name=name, region=region, token=api_token)


def _saved_token(*, name: str, region: str, token: str) -> SavedToken:
    """Build a validated token and normalize validation for Click callers."""
    try:
        return SavedToken(
            name=validate_user_token_name(name),
            region=region,
            token=token,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from None


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
    token: str = click.prompt("\nPaste your SCCFM API token", hide_input=True)
    token = token.strip()
    if not token:
        raise click.ClickException("API token cannot be empty.")
    return token


def _prompt_token_name() -> str:
    """Ask for a label to identify this token."""
    while True:
        name: str = click.prompt(
            "\nName for this token (for your reference)",
            default="default",
        )
        try:
            return validate_user_token_name(name)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")


# ── .env file management ────────────────────────────────────────


def _upsert_env_var(content: str, var: str, value: str) -> str:
    """Replace ``export VAR=…`` in *content*, or append if not present."""
    pattern = rf"^[ \t]*(?:export[ \t]+)?{var}[ \t]*=.*$"
    replacement = f"export {var}={value}"
    updated, count = re.subn(
        pattern,
        lambda _match: replacement,
        content,
        flags=re.MULTILINE,
    )
    if count > 1:
        lines = updated.splitlines(keepends=True)
        seen = False
        deduplicated: list[str] = []
        assignment = re.compile(pattern)
        for line in lines:
            if assignment.fullmatch(line.rstrip("\r\n")):
                if seen:
                    continue
                seen = True
            deduplicated.append(line)
        updated = "".join(deduplicated)
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
    transaction_content = _read_transaction_text(env_path)
    if _transaction_manages(env_path):
        content = transaction_content
    else:
        if env_path.is_symlink():
            raise click.ClickException(
                f"Refusing to update a symlinked credential file: {env_path}"
            )
        if env_path.exists() and not env_path.is_file():
            raise click.ClickException(f"Credential path is not a regular file: {env_path}")
        content = env_path.read_text() if env_path.exists() else None

    if content is not None:
        pass
    elif example_path.exists():
        content = example_path.read_text()
    else:
        content = (
            "# Auto-generated by change-tokens — do not commit\n"
            "# The .env file is gitignored and loaded automatically by direnv\n\n"
        )

    content = _upsert_env_var(content, "SCCFM_REGION", shlex.quote(region))
    content = _upsert_env_var(content, "SCCFM_API_TOKEN", shlex.quote(api_token))
    _write_private_text(env_path, content)
    console.print(f"[green]Updated .env file:[/green] {env_path}")
    return env_path


# ── CLI config management ────────────────────────────────────────


def _update_cli_config(region: str, api_token: str, profile: str = "default") -> None:
    """Update the sccfm-cli config so CLI commands use the same token."""
    from cisco_sccfm_cli.models import Config
    from cisco_sccfm_cli.services import ConfigService

    config = Config(profile=profile, region=region, api_token=api_token)
    config_path = _resolved_config_path()
    if _transaction_manages(config_path):
        if _is_default_config_path(config_path) and _active_credential_transaction is not None:
            parent_descriptor = _active_credential_transaction.parent_descriptor(config_path)
            if parent_descriptor is not None:
                os.fchmod(parent_descriptor, 0o700)
        content = _read_transaction_text(config_path)
        try:
            payload = {} if content is None else json.loads(content)
        except json.JSONDecodeError:
            raise
        profiles = payload.get("profiles", {})
        if not isinstance(profiles, dict):
            profiles = {}
        profiles[profile] = {"region": region, "api_token": api_token}
        _write_private_text(
            config_path,
            json.dumps({"profiles": profiles}, indent=2),
        )
    else:
        ConfigService(path=config_path).save(config)
    console.print(f"[green]Updated CLI config profile '{profile}'[/green]")


def _is_default_config_path(config_path: Path) -> bool:
    """Return whether the configured location is the CLI's default private path."""
    return _platform_normalized_path(config_path) == _platform_normalized_path(
        Path.home() / ".sccfm-cli" / "config.json"
    )


# ── Vault password management ────────────────────────────────────


def _ensure_vault_pass(examples_path: Path) -> Path:
    """Return the vault password file, creating it interactively if needed."""
    vault_pass_path = examples_path / ".vault_pass"

    if vault_pass_path.is_symlink():
        raise click.ClickException(
            f"Refusing to use a symlinked credential file: {vault_pass_path}"
        )
    if vault_pass_path.exists():
        if not vault_pass_path.is_file():
            raise click.ClickException(
                f"Vault password path is not a regular file: {vault_pass_path}"
            )
        vault_pass_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
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

    _write_private_text(vault_pass_path, password.strip() + "\n")
    console.print(f"[green]Created vault password file:[/green] {vault_pass_path}")
    return vault_pass_path


def _ensure_vault_pass_headless(examples_path: Path, vault_password: str | None) -> Path:
    """Return the vault password file, creating it from *vault_password*
    if it does not already exist.  No interactive prompts.
    """
    vault_pass_path = examples_path / ".vault_pass"

    if vault_pass_path.is_symlink():
        raise click.ClickException(
            f"Refusing to use a symlinked credential file: {vault_pass_path}"
        )
    if vault_pass_path.exists():
        if not vault_pass_path.is_file():
            raise click.ClickException(
                f"Vault password path is not a regular file: {vault_pass_path}"
            )
        vault_pass_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        console.print(f"[dim]Using existing vault password file: {vault_pass_path}[/dim]")
        return vault_pass_path

    if not vault_password or not vault_password.strip():
        raise click.ClickException(
            "No vault password found. Set SCCFM_VAULT_PASSWORD, or create a private "
            ".vault_pass file in the examples directory before retrying."
        )

    _write_private_text(vault_pass_path, vault_password.strip() + "\n")
    console.print(f"[green]Created vault password file:[/green] {vault_pass_path}")
    return vault_pass_path


def _merge_token(store: VaultTokenStore, token: SavedToken) -> list[SavedToken]:
    """Merge *token* into the existing saved list, replacing by name."""
    existing = store.list_tokens()
    if any(saved.name != token.name and saved.token == token.token for saved in existing):
        raise click.ClickException("That API token is already saved under a different name.")
    merged = [t for t in existing if t.name != token.name]
    merged.append(token)
    return merged


# ── vars.yml management ─────────────────────────────────────────


def _update_vars_region(examples_path: Path, region: str) -> None:
    """Set sccfm_region in group_vars/all/vars.yml, preserving other content."""
    vars_path = examples_path / "group_vars" / "all" / "vars.yml"
    transaction_content = _read_transaction_text(vars_path)
    if _transaction_manages(vars_path):
        content = transaction_content
    else:
        if vars_path.is_symlink():
            raise click.ClickException(
                f"Refusing to update a symlinked workspace file: {vars_path}"
            )
        if vars_path.exists() and not vars_path.is_file():
            raise click.ClickException(f"Workspace path is not a regular file: {vars_path}")
        vars_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        content = vars_path.read_text() if vars_path.exists() else None

    if content is not None:
        if re.search(r"^sccfm_region:.*$", content, flags=re.MULTILINE):
            updated = re.sub(
                r"^sccfm_region:.*$",
                f"sccfm_region: {region}",
                content,
                flags=re.MULTILINE,
            )
        else:
            updated = content.rstrip() + f"\nsccfm_region: {region}\n"
        _write_bytes(vars_path, updated.encode("utf-8"), mode=0o644)
    else:
        _write_bytes(
            vars_path,
            (
                "---\n"
                "# Plain variables (not sensitive)\n"
                "# These can be committed to version control\n"
                "\n"
                "# SCCFM connection settings\n"
                f"sccfm_region: {region}\n"
            ).encode("utf-8"),
            mode=0o644,
        )

    console.print(f"[green]Set region to '{region}' in:[/green] {vars_path}")


# ── Headless logic ───────────────────────────────────────────────


def _run_headless(
    region: str,
    api_token: str,
    name: str,
    profile: str,
    vault_password: str | None,
    legacy_region: str | None,
    path: Path | None,
) -> None:
    """Execute the full setup without any interactive prompts."""
    root = _project_root()
    examples_path = _resolve_examples_path(path)
    console.print(f"[dim]Examples directory: {examples_path}[/dim]")

    _verify_ansible_vault()

    # ── Build token ──────────────────────────────────────────────
    selected = _saved_token(name=name, region=region, token=api_token)

    # ── Vault password ───────────────────────────────────────────
    vault_pass_path = _ensure_vault_pass_headless(examples_path, vault_password)

    # ── Merge with existing saved tokens ─────────────────────────
    store = VaultTokenStore(examples_path, migration_region=legacy_region)
    try:
        all_tokens = _merge_token(store, selected)
    except ActiveTokenRegionRequired as exc:
        raise click.ClickException(
            f"{exc}. Set SCCFM_LEGACY_REGION or pass --legacy-region with the region of the "
            "existing active-only Vault token."
        ) from None

    # ── Write files ──────────────────────────────────────────────
    with _credential_transaction(_credential_transaction_paths(root, examples_path)):
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
    summary.add_row("CLI config", str(_resolved_config_path()))

    console.print()
    console.print(summary)


# ── CLI entry point ──────────────────────────────────────────────

_VALID_REGIONS = tuple(_REGIONS)


@click.command(
    help="Setup SCCFM API tokens, .env, and Ansible Vault.\n\n"
    "Runs interactively by default. Supply --region with SCCFM_API_TOKEN "
    "to run in headless mode (no prompts).",
)
@click.option(
    "--region",
    "-r",
    default=None,
    type=click.Choice(_VALID_REGIONS, case_sensitive=False),
    help="SCCFM region. Enables headless mode when combined with SCCFM_API_TOKEN.",
)
@click.option(
    "--api-token",
    "-t",
    default=None,
    envvar="SCCFM_API_TOKEN",
    show_envvar=True,
    hide_input=True,
    help=(
        "SCCFM API token. Passing it directly is supported for compatibility but may expose it "
        "in process listings and shell history; prefer SCCFM_API_TOKEN."
    ),
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
    envvar="SCCFM_VAULT_PASSWORD",
    show_envvar=True,
    hide_input=True,
    help=(
        "Vault password used only when a private .vault_pass file does not exist. Passing "
        "--vault-password directly is supported for compatibility but may expose it in process "
        "listings and shell history; prefer SCCFM_VAULT_PASSWORD or an existing private "
        ".vault_pass file."
    ),
)
@click.option(
    "--legacy-region",
    default=None,
    envvar="SCCFM_LEGACY_REGION",
    show_envvar=True,
    type=click.Choice(_VALID_REGIONS, case_sensitive=False),
    help=(
        "Region of an existing active-only Vault token when its region cannot be resolved. "
        "This is distinct from --region, which belongs to the newly selected token."
    ),
)
@click.option(
    "--path",
    default=None,
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=True,
        resolve_path=True,
        path_type=Path,
    ),
    help=f"Path to the ansible examples directory (default: {_DEFAULT_EXAMPLES_PATH}).",
)
def main(
    region: str | None,
    api_token: str | None,
    name: str,
    profile: str,
    vault_password: str | None,
    legacy_region: str | None,
    path: Path | None,
) -> None:
    """Setup tokens — auto-detects interactive vs headless mode."""
    ctx = click.get_current_context()
    if (
        api_token is not None
        and ctx.get_parameter_source("api_token") is ParameterSource.COMMANDLINE
    ):
        click.echo(
            "Warning: passing --api-token directly may expose it in process listings and "
            "shell history; prefer SCCFM_API_TOKEN.",
            err=True,
        )
    if (
        vault_password is not None
        and ctx.get_parameter_source("vault_password") is ParameterSource.COMMANDLINE
    ):
        click.echo(
            "Warning: passing --vault-password directly may expose it in process listings and "
            "shell history; prefer SCCFM_VAULT_PASSWORD or an existing private .vault_pass file.",
            err=True,
        )

    headless = region is not None or api_token is not None

    if headless:
        if not region or not api_token:
            raise click.UsageError(
                "Headless mode requires --region and an API token from SCCFM_API_TOKEN "
                "or the legacy --api-token option."
            )
        _run_headless(
            region=region,
            api_token=api_token,
            name=name,
            profile=profile,
            vault_password=vault_password,
            legacy_region=legacy_region,
            path=path,
        )
    else:
        try:
            _run_setup(path)
        except (KeyboardInterrupt, click.Abort):
            console.print("\n[dim]Cancelled.[/dim]")


def _run_setup(path: Path | None) -> None:
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
    try:
        selected, all_tokens = _select_or_create_token(store)
    except ActiveTokenRegionRequired:
        console.print(
            "[yellow]The existing active-only Vault token needs its SCCFM region before it "
            "can be preserved.[/yellow]"
        )
        migration_region = _prompt_region()
        store = VaultTokenStore(examples_path, migration_region=migration_region)
        selected, all_tokens = _select_or_create_token(store)

    region = selected.region
    api_token = selected.token
    token_name = selected.name

    # ── Write files ──────────────────────────────────────────────
    with _credential_transaction(_credential_transaction_paths(root, examples_path)):
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
    summary.add_row("CLI config", str(_resolved_config_path()))

    console.print()
    console.print(summary)
    console.print(
        "\n[green]You can now run playbooks with:[/green]\n"
        f"  ansible-playbook -i {examples_path / 'inventory.sccfm.yml'} \\\n"
        f"    {examples_path / 'show_devices.yml'} "
        f"--vault-password-file {examples_path / '.vault_pass'}"
    )


if __name__ == "__main__":
    main()

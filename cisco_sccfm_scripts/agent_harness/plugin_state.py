# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Inspect and refresh the locally installed SCCFM Codex plugin."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PLUGIN_ID = "sccfm@sccfm-devkit"
PLUGIN_NAME = "sccfm"
IGNORED_PARTS = {"__pycache__", ".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


@dataclass(frozen=True)
class PluginFreshness:
    """Comparison between repository plugin source and the installed cache."""

    plugin_id: str
    version: str
    marketplace: str
    source_path: str
    cache_path: str
    source_digest: str
    installed_digest: str | None
    fresh: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Return report-ready metadata."""

        return asdict(self)


def plugin_record(payload: str, plugin_id: str = PLUGIN_ID) -> dict[str, Any] | None:
    """Return one enabled installed plugin record from `codex plugin list`."""

    parsed = json.loads(payload)
    installed = parsed.get("installed", []) if isinstance(parsed, dict) else []
    for item in installed:
        if (
            isinstance(item, dict)
            and item.get("pluginId") == plugin_id
            and item.get("installed")
            and item.get("enabled")
        ):
            return item
    return None


def inspect_plugin_freshness(
    payload: str,
    repository_root: Path,
    codex_home: Path | None = None,
) -> PluginFreshness:
    """Compare the checkout plugin with the exact version Codex cached."""

    record = plugin_record(payload)
    if record is None:
        raise ValueError(f"{PLUGIN_ID} is not installed and enabled")
    version = _required_text(record, "version")
    marketplace = _required_text(record, "marketplaceName")
    source = record.get("source")
    source_path = _required_text(source, "path") if isinstance(source, dict) else ""
    plugin_source = (repository_root / "plugins" / PLUGIN_NAME).resolve()
    cache_root = codex_home or Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    cache_path = cache_root / "plugins" / "cache" / marketplace / PLUGIN_NAME / version
    source_digest = plugin_tree_digest(plugin_source)
    installed_digest = plugin_tree_digest(cache_path) if cache_path.is_dir() else None
    source_matches = Path(source_path).resolve() == plugin_source if source_path else False
    fresh = source_matches and installed_digest == source_digest
    if not source_matches:
        reason = f"installed source is {source_path or 'unknown'}, not this checkout"
    elif installed_digest is None:
        reason = f"installed cache directory is missing: {cache_path}"
    elif installed_digest != source_digest:
        reason = "installed cache differs from the plugin source in this checkout"
    else:
        reason = "installed cache matches this checkout"
    return PluginFreshness(
        plugin_id=PLUGIN_ID,
        version=version,
        marketplace=marketplace,
        source_path=source_path,
        cache_path=str(cache_path),
        source_digest=source_digest,
        installed_digest=installed_digest,
        fresh=fresh,
        reason=reason,
    )


def refresh_local_plugin(codex: str, repository_root: Path, payload: str) -> str:
    """Apply a Codex cachebuster and reinstall a confirmed local plugin."""

    record = plugin_record(payload)
    if record is None:
        raise ValueError(f"{PLUGIN_ID} is not installed and enabled")
    marketplace = _required_text(record, "marketplaceName")
    source = record.get("source")
    marketplace_source = record.get("marketplaceSource")
    expected_plugin = (repository_root / "plugins" / PLUGIN_NAME).resolve()
    if (
        not isinstance(source, dict)
        or Path(_required_text(source, "path")).resolve() != expected_plugin
    ):
        raise ValueError("refusing to refresh a plugin that does not point at this checkout")
    if (
        not isinstance(marketplace_source, dict)
        or marketplace_source.get("sourceType") != "local"
        or Path(_required_text(marketplace_source, "source")).resolve() != repository_root.resolve()
    ):
        raise ValueError("refusing to refresh a plugin from a non-local marketplace")

    manifest_path = expected_plugin / ".codex-plugin" / "plugin.json"
    original_manifest = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(original_manifest)
    installed_version = _required_text(record, "version")
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    cache_root = codex_home / "plugins" / "cache" / marketplace / PLUGIN_NAME
    installed_cache = cache_root / installed_version
    base_version = installed_version.partition("+")[0]
    cachebuster = datetime.now(UTC).strftime("local-%Y%m%d-%H%M%S")
    manifest["version"] = f"{base_version}+codex.{cachebuster}"
    with tempfile.TemporaryDirectory(prefix="sccfm-plugin-cache-backup-") as backup_text:
        backup_root = Path(backup_text) / "versions"
        cached_versions = (
            [path for path in cache_root.iterdir() if path.is_dir()] if cache_root.is_dir() else []
        )
        if installed_cache.is_dir() and installed_cache not in cached_versions:
            cached_versions.append(installed_cache)
        for cached_version in cached_versions:
            shutil.copytree(cached_version, backup_root / cached_version.name)
        _write_manifest(manifest_path, json.dumps(manifest, indent=2) + "\n")
        try:
            completed = subprocess.run(
                [codex, "plugin", "add", f"{PLUGIN_NAME}@{marketplace}", "--json"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            _write_manifest(manifest_path, original_manifest)
            raise
        finally:
            if backup_root.is_dir():
                for backup in backup_root.iterdir():
                    destination = cache_root / backup.name
                    if not destination.exists():
                        shutil.copytree(backup, destination)
        if completed.returncode != 0:
            _write_manifest(manifest_path, original_manifest)
            raise ValueError(
                "plugin refresh failed: " + (completed.stderr.strip() or completed.stdout.strip())
            )
        return completed.stdout


def plugin_tree_digest(root: Path) -> str:
    """Hash stable plugin source files and their relative paths."""

    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if IGNORED_PARTS.intersection(relative.parts) or path.suffix in IGNORED_SUFFIXES:
            continue
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"plugin metadata is missing {key}")
    return value


def _write_manifest(path: Path, content: str) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)

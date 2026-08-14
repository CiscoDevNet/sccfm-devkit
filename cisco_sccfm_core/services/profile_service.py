# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping

from cisco_sccfm_core.models.profile import Profile

_CONFIG_DIR = Path.home() / ".sccfm-cli"
_CONFIG_FILE = _CONFIG_DIR / "config.json"
_CONFIG_DIR_MODE = 0o700
_CONFIG_FILE_MODE = 0o600


class ProfileService:
    """Read and write SCCFM profiles from the canonical local config file."""

    def __init__(self, path: Path | None = None) -> None:
        configured_path = os.environ.get("SCCFM_CONFIG")
        self._path = path or (
            Path(configured_path).expanduser() if configured_path else _CONFIG_FILE
        )
        self._harden_existing_path()

    def load(self, profile: str) -> Profile | None:
        profiles = self._load_profiles()
        profile_data = profiles.get(profile)
        if not profile_data:
            return None
        return Profile(
            profile=profile,
            region=profile_data["region"],
            api_token=profile_data["api_token"],
        )

    def save(self, config: Profile) -> None:
        profiles = self._load_profiles()
        profiles[config.profile] = {
            "region": config.region,
            "api_token": config.api_token,
        }
        self._persist({"profiles": profiles})

    def list_profiles(self) -> list[Profile]:
        profiles = self._load_profiles()
        return [
            Profile(profile=name, region=data["region"], api_token=data["api_token"])
            for name, data in sorted(profiles.items())
        ]

    def remove(self, profile: str) -> bool:
        """Remove *profile*, returning whether it existed."""
        profiles = self._load_profiles()
        if profile not in profiles:
            return False
        del profiles[profile]
        self._persist({"profiles": profiles})
        return True

    def _load_profiles(self) -> Dict[str, Dict[str, Any]]:
        if not self._path.exists():
            return {}
        with self._path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return dict(data.get("profiles", {}))

    def _persist(self, payload: Mapping[str, Any]) -> None:
        self._ensure_config_directory()
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=self._path.parent,
            prefix=f".{self._path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        try:
            os.fchmod(file_descriptor, _CONFIG_FILE_MODE)
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary_path.replace(self._path)
            self._path.chmod(_CONFIG_FILE_MODE)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    def _ensure_config_directory(self) -> None:
        created = not self._path.parent.exists()
        self._path.parent.mkdir(parents=True, mode=_CONFIG_DIR_MODE, exist_ok=True)
        if created or self._path.parent == _CONFIG_DIR:
            self._path.parent.chmod(_CONFIG_DIR_MODE)

    def _harden_existing_path(self) -> None:
        if self._path.is_file():
            self._path.chmod(_CONFIG_FILE_MODE)
        if self._path.parent == _CONFIG_DIR and self._path.parent.is_dir():
            self._path.parent.chmod(_CONFIG_DIR_MODE)

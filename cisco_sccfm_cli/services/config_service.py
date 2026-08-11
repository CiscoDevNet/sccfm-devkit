# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, TextIO

from cisco_sccfm_cli.models import Config

_CONFIG_DIR = Path.home() / ".sccfm-cli"
_CONFIG_FILE = _CONFIG_DIR / "config.json"
_CONFIG_DIR_MODE = 0o700
_CONFIG_FILE_MODE = 0o600


class ConfigService:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _CONFIG_FILE
        self._uses_default_path = self._path == _CONFIG_FILE

    def load(self, profile: str) -> Config | None:
        profiles = self._load_profiles()
        profile_data = profiles.get(profile)
        if not profile_data:
            return None
        return Config(
            profile=profile,
            region=profile_data["region"],
            api_token=profile_data["api_token"],
        )

    def save(self, config: Config) -> None:
        profiles = self._load_profiles()
        profiles[config.profile] = {
            "region": config.region,
            "api_token": config.api_token,
        }
        self._persist({"profiles": profiles})

    def list_profiles(self) -> list[Config]:
        profiles = self._load_profiles()
        return [
            Config(profile=name, region=data["region"], api_token=data["api_token"])
            for name, data in sorted(profiles.items())
        ]

    def _load_profiles(self) -> Dict[str, Dict[str, Any]]:
        self._harden_existing_storage()
        if not self._path.exists():
            return {}
        with self._path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return dict(data.get("profiles", {}))

    def _persist(self, payload: Mapping[str, Any]) -> None:
        self._ensure_parent_directory()
        self._harden_existing_file()
        with self._open_directly_for_write() as handle:
            json.dump(payload, handle, indent=2)

    def _ensure_parent_directory(self) -> None:
        created = False
        try:
            self._path.parent.mkdir(parents=True, mode=_CONFIG_DIR_MODE)
            created = True
        except FileExistsError:
            if not self._path.parent.is_dir():
                raise

        if self._supports_posix_permissions() and (created or self._uses_default_path):
            self._path.parent.chmod(_CONFIG_DIR_MODE)

    def _harden_existing_storage(self) -> None:
        if not self._supports_posix_permissions():
            return
        if self._uses_default_path and self._path.parent.exists():
            self._path.parent.chmod(_CONFIG_DIR_MODE)
        self._harden_existing_file()

    def _harden_existing_file(self) -> None:
        if self._supports_posix_permissions() and self._path.exists():
            self._path.chmod(_CONFIG_FILE_MODE)

    def _open_directly_for_write(self) -> TextIO:
        if not self._supports_posix_permissions():
            return self._path.open("w", encoding="utf-8")

        descriptor = os.open(
            self._path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            _CONFIG_FILE_MODE,
        )
        try:
            os.fchmod(descriptor, _CONFIG_FILE_MODE)
            return os.fdopen(descriptor, "w", encoding="utf-8")
        except BaseException:
            os.close(descriptor)
            raise

    @staticmethod
    def _supports_posix_permissions() -> bool:
        return os.name == "posix"

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

from sccfm_cli.models import Config

_CONFIG_DIR = Path.home() / ".sccfm-cli"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


class ConfigService:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _CONFIG_FILE

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
        if not self._path.exists():
            return {}
        with self._path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return dict(data.get("profiles", {}))

    def _persist(self, payload: Mapping[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

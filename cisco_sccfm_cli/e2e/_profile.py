# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Resolve the canonical SCCFM profile used by the CLI e2e suite."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from cisco_sccfm_cli.e2e._state import PhaseStateStore
from cisco_sccfm_core.services.profile_service import ProfileService


@dataclass(frozen=True)
class ProfileContext:
    profile: str
    config_path: Path
    region: str
    state: PhaseStateStore


def resolve_profile() -> ProfileContext:
    """Load the configured e2e profile without copying its token."""
    profile_name = os.environ.get("SCCFM_E2E_PROFILE", "default")
    config_path = Path(
        os.environ.get("SCCFM_CONFIG", str(Path.home() / ".sccfm-cli" / "config.json"))
    ).expanduser()
    profile = ProfileService(config_path).load(profile_name)
    if profile is None:
        raise RuntimeError(
            f"E2E profile '{profile_name}' not found in {config_path}. "
            f"Run 'sccfm-cli --profile {profile_name} configure' first."
        )
    return ProfileContext(
        profile=profile.profile,
        config_path=config_path,
        region=profile.region,
        state=PhaseStateStore(),
    )

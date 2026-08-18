# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .dependencies import ensure_required_dependencies, record_import_error

try:
    from cisco_sccfm_core.services.profile_service import ProfileService
except ImportError as exc:
    record_import_error(exc)

if TYPE_CHECKING:
    from ansible.module_utils.basic import AnsibleModule

ALLOWED_REGIONS = ("int", "us", "eu", "apj", "au", "uae", "in", "ci")
REGION_ALIASES = {"aus": "au"}
ALLOWED_REGIONS_TEXT = ", ".join(ALLOWED_REGIONS)


def _normalize_region(region: str | None) -> str | None:
    """Normalize a region without requiring the separately installed core package."""
    if region is None:
        return None
    normalized = region.strip().lower()
    return REGION_ALIASES.get(normalized, normalized)


@dataclass(frozen=True)
class Config:
    """Validated SCCFM API configuration resolved from a named profile."""

    region: str = ""
    api_token: str = ""

    def __post_init__(self) -> None:
        resolved_region = _normalize_region(self.region)
        resolved_token = self.api_token

        # Use object.__setattr__ since dataclass is frozen
        object.__setattr__(self, "region", resolved_region)
        object.__setattr__(self, "api_token", resolved_token)

        # Validate
        if not self.api_token:
            raise ValueError(
                "The selected SCCFM profile does not contain an API token. "
                "Generate an API token following instructions in "
                "https://developer.cisco.com/docs/cisco-security-cloud-control-firewall-manager/"
                "authentication/"
            )
        if not self.region:
            raise ValueError(
                "The selected SCCFM profile does not contain a region. "
                f"Allowed regions: {ALLOWED_REGIONS_TEXT}"
            )
        if self.region not in ALLOWED_REGIONS:
            raise ValueError(f"SCCFM region must be one of: {ALLOWED_REGIONS_TEXT}")


def base_argument_spec() -> dict[str, dict[str, Any]]:
    """Return common argument spec for canonical SCCFM profile selection.

    Returns:
        Dictionary suitable for merging into build_argument_spec().
    """
    return {
        "profile": {"type": "str", "required": False, "default": "default"},
        "config_path": {"type": "path", "required": False},
    }


def identifier_argument_spec() -> dict[str, dict[str, Any]]:
    """Return argument spec for uid/name identifier fields.

    Returns:
        Dictionary suitable for merging into build_argument_spec().
    """
    return {
        "uid": {"type": "str", "required": False},
        "name": {"type": "str", "required": False},
    }


def create_config(module: "AnsibleModule") -> Config:
    """Resolve a named profile and create a Config, with error handling.

    Args:
        module: The AnsibleModule instance.

    Returns:
        A validated Config instance.

    Note:
        On validation error, calls module.fail_json() and does not return.
    """
    ensure_required_dependencies(module)

    try:
        profile = module.params.get("profile") or "default"
        raw_path = module.params.get("config_path")
        stored = ProfileService(path=Path(raw_path) if raw_path else None).load(profile)
        if stored is None:
            raise ValueError(
                f"SCCFM profile '{profile}' not found. "
                f"Run 'sccfm-cli --profile {profile} configure' to set it up."
            )
        return Config(region=stored.region, api_token=stored.api_token)
    except (OSError, ValueError) as e:
        module.fail_json(msg=str(e))
        raise

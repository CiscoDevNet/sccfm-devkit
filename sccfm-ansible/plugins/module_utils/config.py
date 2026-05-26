# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sccfm_core.constants import SCCFM_REGIONS, normalize_sccfm_region

if TYPE_CHECKING:
    from ansible.module_utils.basic import AnsibleModule

ALLOWED_REGIONS = SCCFM_REGIONS
ALLOWED_REGIONS_TEXT = ", ".join(ALLOWED_REGIONS)


@dataclass(frozen=True)
class Config:
    """SCCFM API configuration.

    If region or api_token are empty, falls back to environment variables.
    Validates region and api_token on construction.
    """

    region: str = ""
    api_token: str = ""

    def __post_init__(self) -> None:
        # Resolve from environment if not provided
        resolved_region = normalize_sccfm_region(self.region or os.getenv("SCCFM_REGION"))
        resolved_token = self.api_token or os.getenv("SCCFM_API_TOKEN")

        # Use object.__setattr__ since dataclass is frozen
        object.__setattr__(self, "region", resolved_region)
        object.__setattr__(self, "api_token", resolved_token)

        # Validate
        if not self.api_token:
            raise ValueError(
                "api_token is required. Provide it via module parameter, module_defaults, or "
                "SCCFM_API_TOKEN environment variable. "
                "Generate an API token following instructions in "
                "https://developer.cisco.com/docs/cisco-security-cloud-control-firewall-manager/"
                "authentication/"
            )
        if not self.region:
            raise ValueError(
                f"region is required. Provide it via module parameter, module_defaults, or "
                f"SCCFM_REGION environment variable. Allowed regions: {ALLOWED_REGIONS_TEXT}"
            )
        if self.region not in ALLOWED_REGIONS:
            raise ValueError(f"SCCFM region must be one of: {ALLOWED_REGIONS_TEXT}")


def base_argument_spec() -> dict[str, dict[str, Any]]:
    """Return common argument spec for region and api_token.

    Returns:
        Dictionary suitable for merging into build_argument_spec().
    """
    return {
        "region": {"type": "str", "required": False},
        "api_token": {"type": "str", "required": False, "no_log": True},
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
    """Create a Config from module params, with error handling.

    Args:
        module: The AnsibleModule instance.

    Returns:
        A validated Config instance.

    Note:
        On validation error, calls module.fail_json() and does not return.
    """
    try:
        return Config(
            region=module.params.get("region") or "",
            api_token=module.params.get("api_token") or "",
        )
    except ValueError as e:
        module.fail_json(msg=str(e))
        raise

from __future__ import annotations

import os
from dataclasses import dataclass

ALLOWED_REGIONS = ("int", "us", "eu", "apj", "aus", "uae", "in")


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
        resolved_region = self.region or os.getenv("SCCFM_REGION")
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
            allowed = ", ".join(ALLOWED_REGIONS)
            raise ValueError(
                f"region is required. Provide it via module parameter, module_defaults, or "
                f"SCCFM_REGION environment variable. Allowed regions: {allowed}"
            )
        if self.region not in ALLOWED_REGIONS:
            allowed = ", ".join(ALLOWED_REGIONS)
            raise ValueError(f"SCCFM region must be one of: {allowed}")

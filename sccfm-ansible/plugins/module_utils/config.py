from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ansible.module_utils.basic import AnsibleModule

ALLOWED_REGIONS = ("int", "us", "eu", "apj", "aus", "uae", "in")


@dataclass(frozen=True)
class Config:
    """SCCFM API configuration.

    Validates region and api_token on construction.
    """

    region: str
    api_token: str

    def __post_init__(self) -> None:
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
                "region is required. Provide it via module parameter, module_defaults, or "
                "SCCFM_REGION environment variable."
            )
        if self.region not in ALLOWED_REGIONS:
            allowed = ", ".join(ALLOWED_REGIONS)
            raise ValueError(f"SCCFM region must be one of: {allowed}")


def resolve_connection_params(module: AnsibleModule) -> tuple[str, str]:
    """Get region and api_token from module params or environment.

    Resolution order: module param -> environment variable -> empty string.

    Returns:
        Tuple of (region, api_token)
    """
    region = module.params.get("region") or os.getenv("SCCFM_REGION") or ""
    api_token = module.params.get("api_token") or os.getenv("SCCFM_API_TOKEN") or ""
    return region, api_token

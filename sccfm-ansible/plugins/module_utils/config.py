from __future__ import annotations

from dataclasses import dataclass

ALLOWED_REGIONS = ("int", "us", "eu", "apj", "aus", "uae", "in")


@dataclass(frozen=True)
class Config:
    region: str
    api_token: str

    def __post_init__(self) -> None:
        if not self.api_token:
            raise ValueError(
                "SCCFM api_token is required. Generate an API token following instructions in "
                "https://developer.cisco.com/docs/cisco-security-cloud-control-firewall-manager/"
                "authentication/"
            )
        if self.region not in ALLOWED_REGIONS:
            allowed = ", ".join(ALLOWED_REGIONS)
            raise ValueError(f"SCCFM region must be one of: {allowed}")

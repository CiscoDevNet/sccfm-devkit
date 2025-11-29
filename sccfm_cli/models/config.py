from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    profile: str
    region: str
    api_token: str

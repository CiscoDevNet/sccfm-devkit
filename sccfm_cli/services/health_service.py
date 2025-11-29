from __future__ import annotations

from dataclasses import dataclass
from typing import List

from scc_firewall_manager_sdk import UsersApi

from sccfm_cli.factories import ApiClientFactory
from sccfm_cli.models import Config


@dataclass(frozen=True)
class HealthStatus:
    name: str
    healthy: bool
    detail: str


class HealthService:
    def __init__(self, config: Config) -> None:
        api_client = ApiClientFactory().build(config)
        self.users_api = UsersApi(api_client)

    def check(self) -> List[HealthStatus]:
        try:
            self.users_api.get_token()
            return [HealthStatus(name="API connectivity", healthy=True, detail="Token valid")]
        except Exception:
            return [
                HealthStatus(name="API connectivity", healthy=False, detail="Token invalid"),
            ]

from __future__ import annotations

import json
from dataclasses import dataclass

from scc_firewall_manager_sdk import ApiClient

from sccfm_core.factories import ApiClientFactory
from sccfm_core.types import ConfigLike


@dataclass
class FmcAccessPolicy:
    uid: str
    name: str


class CdfmcAccessPolicyService:
    def __init__(self, config: ConfigLike) -> None:
        self._api_client: ApiClient = ApiClientFactory().build(config)

    def get_access_policies(self, domain_uid: str) -> list[FmcAccessPolicy]:
        resource_path = f"/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/policy/accesspolicies"
        params = self._api_client.param_serialize(
            method="GET",
            resource_path=resource_path,
            path_params=None,
            query_params=None,
            header_params={"Accept": "application/json"},
            body=None,
            post_params=None,
            files=None,
            auth_settings=["bearerAuth"],
            collection_formats=None,
        )
        response = self._api_client.call_api(*params)
        response.read()  # type: ignore[no-untyped-call]
        data = json.loads(response.data)
        return [
            FmcAccessPolicy(uid=item["id"], name=item["name"]) for item in data.get("items", [])
        ]

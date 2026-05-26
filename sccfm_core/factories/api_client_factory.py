# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from scc_firewall_manager_sdk import ApiClient, Configuration

from sccfm_core.types import ConfigLike

_REGION_HOSTS: dict[str, str] = {
    "ci": "https://ci.manage.security.cisco.com/api/rest",
}

_DEFAULT_HOST_TEMPLATE = "https://api.{region}.security.cisco.com/firewall"


class ApiClientFactory:
    @staticmethod
    def build(config: ConfigLike) -> ApiClient:
        host = _REGION_HOSTS.get(
            config.region,
            _DEFAULT_HOST_TEMPLATE.format(region=config.region),
        )
        return ApiClient(
            Configuration(
                host=host,
                access_token=config.api_token,
            )
        )

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Shared helper for policy API operations.

Provides common HTTP response handling used by AccessRuleService
via composition.
"""

from __future__ import annotations

import json
from typing import Any

from scc_firewall_manager_sdk.api.asa_access_groups_api import ASAAccessGroupsApi
from scc_firewall_manager_sdk.api.asa_access_rules_api import ASAAccessRulesApi
from scc_firewall_manager_sdk.exceptions import ApiException

from sccfm_core.factories import ApiClientFactory
from sccfm_core.types import ConfigLike


class PolicyApiHelper:
    """Composable helper wrapping the policy APIs with raw response handling.

    Encapsulates the common pattern of reading raw HTTP responses and
    parsing JSON — needed because the SDK's oneOf deserialization is unreliable.
    """

    def __init__(self, config: ConfigLike) -> None:
        api_client = ApiClientFactory().build(config)
        self.rules_api = ASAAccessRulesApi(api_client)
        self.groups_api = ASAAccessGroupsApi(api_client)

    def read_raw_response(self, response: Any) -> dict[str, Any]:
        """Read and validate a raw HTTP response, returning parsed JSON."""
        raw_data = response.read()
        body = raw_data.decode("utf-8")
        _raise_for_status(response.status, body)
        return dict(json.loads(body))

    def check_raw_response(self, response: Any) -> None:
        """Read and validate a raw HTTP response that may have an empty body."""
        raw_data = response.read()
        body = raw_data.decode("utf-8")
        _raise_for_status(response.status, body)


def _raise_for_status(status: int, body: str) -> None:
    """Raise an ApiException if the HTTP status indicates an error."""
    if 200 <= status < 300:
        return
    raise ApiException(status=status, body=body)

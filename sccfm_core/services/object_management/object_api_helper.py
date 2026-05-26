# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Shared helper for object management API operations.

Provides common HTTP response handling used by both NetworkObjectService
and NetworkGroupService via composition.
"""

from __future__ import annotations

import json
from typing import Any

from scc_firewall_manager_sdk.api.object_management_api import ObjectManagementApi
from scc_firewall_manager_sdk.exceptions import ApiException

from sccfm_core.factories import ApiClientFactory
from sccfm_core.types import ConfigLike


class ObjectApiHelper:
    """Composable helper wrapping the ObjectManagementApi with raw response handling.

    Encapsulates the common pattern of reading raw HTTP responses and
    parsing JSON — needed because the SDK's oneOf deserialization is unreliable.
    """

    def __init__(self, config: ConfigLike) -> None:
        api_client = ApiClientFactory().build(config)
        self.api = ObjectManagementApi(api_client)

    def read_raw_response(self, response: Any) -> dict[str, Any]:
        """Read and validate a raw HTTP response, returning parsed JSON."""
        raw_data = response.read()
        body = raw_data.decode("utf-8")
        raise_for_status(response.status, body)
        return dict(json.loads(body))

    def check_raw_response(self, response: Any) -> None:
        """Read and validate a raw HTTP response that may have an empty body."""
        raw_data = response.read()
        body = raw_data.decode("utf-8")
        raise_for_status(response.status, body)


def raise_for_status(status: int, body: str) -> None:
    """Raise an ApiException if the HTTP status indicates an error."""
    if 200 <= status < 300:
        return
    raise ApiException(status=status, body=body)

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock

from sccfm_core.services.inventory.cdfmc_access_policy_service import (
    CdfmcAccessPolicyService,
)


def _mock_api_response(data: dict[str, Any]) -> Mock:
    response = Mock()
    response.data = json.dumps(data).encode("utf-8")
    response.read.return_value = None
    return response


def test_get_access_policies_passes_pagination_and_returns_page() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("GET", "https://example.test", {}, None, [])
    api_client.call_api.return_value = _mock_api_response(
        {
            "items": [{"id": "policy-1", "name": "Default Access Policy"}],
            "paging": {"count": 10, "limit": 5, "offset": 5},
        }
    )
    service = CdfmcAccessPolicyService.__new__(CdfmcAccessPolicyService)
    service._api_client = api_client

    page = service.get_access_policies("domain-1", limit=5, offset=5)

    assert page.count == 10
    assert page.limit == 5
    assert page.offset == 5
    assert page.items[0].uid == "policy-1"
    api_client.param_serialize.assert_called_once()
    assert api_client.param_serialize.call_args.kwargs["query_params"] == {
        "limit": 5,
        "offset": 5,
    }


def test_get_access_policies_defaults_count_when_paging_is_absent() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("GET", "https://example.test", {}, None, [])
    api_client.call_api.return_value = _mock_api_response(
        {"items": [{"id": "policy-1", "name": "Default Access Policy"}]}
    )
    service = CdfmcAccessPolicyService.__new__(CdfmcAccessPolicyService)
    service._api_client = api_client

    page = service.get_access_policies("domain-1")

    assert page.count == 1
    assert page.limit == 50
    assert page.offset == 0

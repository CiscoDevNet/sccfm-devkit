# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock

import pytest

from cisco_sccfm_core.services.inventory.cdfmc_network_analysis_policy_service import (
    CdfmcNetworkAnalysisPolicyService,
)


def _mock_api_response(data: dict[str, Any]) -> Mock:
    response = Mock()
    response.data = json.dumps(data).encode("utf-8")
    response.read.return_value = None
    return response


def test_list_network_analysis_policies_returns_items() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("GET", "https://example.test", {}, None, [])
    api_client.call_api.return_value = _mock_api_response(
        {"items": [{"id": "nap-1", "name": "Balanced Security and Connectivity"}]}
    )
    service = CdfmcNetworkAnalysisPolicyService.__new__(CdfmcNetworkAnalysisPolicyService)
    service._api_client = api_client

    policies = service.list_network_analysis_policies("domain-1")

    assert len(policies) == 1
    assert policies[0].uid == "nap-1"
    assert policies[0].name == "Balanced Security and Connectivity"
    assert api_client.param_serialize.call_args.kwargs["query_params"] == {"limit": 200}


def test_get_network_analysis_policy_uid_by_name_returns_matching_uid() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("GET", "https://example.test", {}, None, [])
    api_client.call_api.return_value = _mock_api_response(
        {"items": [{"id": "nap-1", "name": "Maximum Detection"}]}
    )
    service = CdfmcNetworkAnalysisPolicyService.__new__(CdfmcNetworkAnalysisPolicyService)
    service._api_client = api_client

    uid = service.get_network_analysis_policy_uid_by_name("domain-1", "Maximum Detection")

    assert uid == "nap-1"


def test_get_network_analysis_policy_uid_by_name_raises_when_missing() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("GET", "https://example.test", {}, None, [])
    api_client.call_api.return_value = _mock_api_response({"items": []})
    service = CdfmcNetworkAnalysisPolicyService.__new__(CdfmcNetworkAnalysisPolicyService)
    service._api_client = api_client

    with pytest.raises(ValueError, match="not found"):
        service.get_network_analysis_policy_uid_by_name("domain-1", "Nonexistent")

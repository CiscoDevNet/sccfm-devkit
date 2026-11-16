# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock

import pytest

from cisco_sccfm_core.services.inventory.cdfmc_network_analysis_intrusion_policy_setting_service import (
    CdfmcNetworkAnalysisAndIntrusionPolicySettingService,
)


def _mock_api_response(data: dict[str, Any]) -> Mock:
    response = Mock()
    response.data = json.dumps(data).encode("utf-8")
    response.read.return_value = None
    return response


_EXISTING_SETTING = {
    "id": "setting-1",
    "type": "NetworkAnalysisAndIntrusionPolicySetting",
    "links": {"self": "https://example.test/.../setting-1"},
    "baseInspection": {
        "baseIpsPolicy": {
            "id": "ips-old",
            "name": "Balanced Security and Connectivity",
            "type": "IntrusionPolicy",
        },
        "baseIpsVariableSet": {"id": "vs-1", "name": "Default-Set", "type": "VariableSet"},
    },
    "networkAnalysis": {
        "defaultNetworkAnalysisPolicy": {
            "id": "nap-old",
            "name": "Balanced Security and Connectivity",
            "type": "NetworkAnalysisPolicy",
        },
        "customNetworkAnalysisRules": [],
    },
    "metadata": {"inheritFromParent": False, "isLockedForChild": False},
}


def test_get_setting_returns_first_item() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("GET", "https://example.test", {}, None, [])
    api_client.call_api.return_value = _mock_api_response({"items": [_EXISTING_SETTING]})
    service = CdfmcNetworkAnalysisAndIntrusionPolicySettingService.__new__(
        CdfmcNetworkAnalysisAndIntrusionPolicySettingService
    )
    service._api_client = api_client

    setting = service.get_setting("domain-1", "policy-1")

    assert setting["id"] == "setting-1"
    resource_path = api_client.param_serialize.call_args.kwargs["resource_path"]
    assert resource_path == (
        "/v1/cdfmc/api/fmc_config/v1/domain/domain-1/policy/accesspolicies/policy-1/"
        "networkanalysisandintrusionpolicysettings"
    )


def test_get_setting_raises_when_no_items() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("GET", "https://example.test", {}, None, [])
    api_client.call_api.return_value = _mock_api_response({"items": []})
    service = CdfmcNetworkAnalysisAndIntrusionPolicySettingService.__new__(
        CdfmcNetworkAnalysisAndIntrusionPolicySettingService
    )
    service._api_client = api_client

    with pytest.raises(ValueError, match="No Network Analysis"):
        service.get_setting("domain-1", "policy-1")


def test_update_setting_mutates_only_the_three_refs_and_puts_to_singular_path() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("PUT", "https://example.test", {}, None, [])
    updated_response = dict(_EXISTING_SETTING)
    api_client.call_api.side_effect = [
        _mock_api_response({"items": [_EXISTING_SETTING]}),
        _mock_api_response(updated_response),
    ]
    service = CdfmcNetworkAnalysisAndIntrusionPolicySettingService.__new__(
        CdfmcNetworkAnalysisAndIntrusionPolicySettingService
    )
    service._api_client = api_client

    new_base_ips_policy = {
        "id": "ips-new",
        "name": "Maximum Detection",
        "type": "IntrusionPolicy",
    }
    new_base_ips_variable_set = {"id": "vs-1", "name": "Default-Set", "type": "VariableSet"}
    new_default_nap = {
        "id": "nap-new",
        "name": "Maximum Detection",
        "type": "NetworkAnalysisPolicy",
    }

    service.update_setting(
        "domain-1",
        "policy-1",
        base_ips_policy=new_base_ips_policy,
        base_ips_variable_set=new_base_ips_variable_set,
        default_network_analysis_policy=new_default_nap,
    )

    assert api_client.call_api.call_count == 2
    put_call_kwargs = api_client.param_serialize.call_args.kwargs
    sent_body = put_call_kwargs["body"]

    # The three refs were replaced...
    assert sent_body["baseInspection"]["baseIpsPolicy"] == new_base_ips_policy
    assert sent_body["baseInspection"]["baseIpsVariableSet"] == new_base_ips_variable_set
    assert sent_body["networkAnalysis"]["defaultNetworkAnalysisPolicy"] == new_default_nap
    # ...but everything else (links, metadata, customNetworkAnalysisRules) is preserved as-is.
    assert sent_body["links"] == _EXISTING_SETTING["links"]
    assert sent_body["metadata"] == _EXISTING_SETTING["metadata"]
    assert sent_body["networkAnalysis"]["customNetworkAnalysisRules"] == []
    assert put_call_kwargs["resource_path"] == (
        "/v1/cdfmc/api/fmc_config/v1/domain/domain-1/policy/accesspolicies/policy-1/"
        "networkanalysisandintrusionpolicysettings/setting-1"
    )

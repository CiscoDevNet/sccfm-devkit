# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock

import pytest

from cisco_sccfm_core.services.inventory.cdfmc_variable_set_service import (
    CdfmcVariableSetService,
)


def _mock_api_response(data: dict[str, Any]) -> Mock:
    response = Mock()
    response.data = json.dumps(data).encode("utf-8")
    response.read.return_value = None
    return response


def test_list_variable_sets_returns_items() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("GET", "https://example.test", {}, None, [])
    api_client.call_api.return_value = _mock_api_response(
        {"items": [{"id": "vs-1", "name": "Default-Set"}]}
    )
    service = CdfmcVariableSetService.__new__(CdfmcVariableSetService)
    service._api_client = api_client

    sets = service.list_variable_sets("domain-1")

    assert len(sets) == 1
    assert sets[0].uid == "vs-1"
    assert sets[0].name == "Default-Set"
    assert api_client.param_serialize.call_args.kwargs["query_params"] == {"limit": 200}


def test_get_variable_set_uid_by_name_returns_matching_uid() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("GET", "https://example.test", {}, None, [])
    api_client.call_api.return_value = _mock_api_response(
        {"items": [{"id": "vs-1", "name": "Default-Set"}]}
    )
    service = CdfmcVariableSetService.__new__(CdfmcVariableSetService)
    service._api_client = api_client

    uid = service.get_variable_set_uid_by_name("domain-1", "Default-Set")

    assert uid == "vs-1"


def test_get_variable_set_uid_by_name_raises_when_missing() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("GET", "https://example.test", {}, None, [])
    api_client.call_api.return_value = _mock_api_response({"items": []})
    service = CdfmcVariableSetService.__new__(CdfmcVariableSetService)
    service._api_client = api_client

    with pytest.raises(ValueError, match="not found"):
        service.get_variable_set_uid_by_name("domain-1", "Nonexistent")

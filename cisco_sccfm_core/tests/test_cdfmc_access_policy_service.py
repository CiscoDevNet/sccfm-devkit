# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock, patch

import pytest
from cisco_sccfm_core.services.inventory.cdfmc_access_policy_service import (
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


def test_create_access_policy_forces_name_and_type_onto_payload() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("POST", "https://example.test", {}, None, [])
    api_client.call_api.return_value = _mock_api_response(
        {"id": "policy-1", "name": "hydra-vftd-BPR-1-AC"}
    )
    service = CdfmcAccessPolicyService.__new__(CdfmcAccessPolicyService)
    service._api_client = api_client

    policy = service.create_access_policy(
        "domain-1",
        "hydra-vftd-BPR-1-AC",
        {"name": "ignored", "type": "ignored", "defaultAction": {"action": "BLOCK"}},
    )

    assert policy.uid == "policy-1"
    assert policy.name == "hydra-vftd-BPR-1-AC"
    sent_body = api_client.param_serialize.call_args.kwargs["body"]
    assert sent_body["name"] == "hydra-vftd-BPR-1-AC"
    assert sent_body["type"] == "AccessPolicy"
    assert sent_body["defaultAction"] == {"action": "BLOCK"}


def test_get_or_create_access_policy_reuses_existing_without_posting() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("GET", "https://example.test", {}, None, [])
    api_client.call_api.return_value = _mock_api_response(
        {"items": [{"id": "policy-1", "name": "hydra-vftd-BPR-1-AC"}]}
    )
    service = CdfmcAccessPolicyService.__new__(CdfmcAccessPolicyService)
    service._api_client = api_client

    policy, created = service.get_or_create_access_policy(
        "domain-1", "hydra-vftd-BPR-1-AC", {"defaultAction": {"action": "BLOCK"}}
    )

    assert created is False
    assert policy.uid == "policy-1"
    api_client.call_api.assert_called_once()


def test_get_or_create_access_policy_creates_when_missing() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("GET", "https://example.test", {}, None, [])
    api_client.call_api.side_effect = [
        _mock_api_response({"items": []}),
        _mock_api_response({"id": "policy-2", "name": "hydra-vftd-BPR-2-AC"}),
    ]
    service = CdfmcAccessPolicyService.__new__(CdfmcAccessPolicyService)
    service._api_client = api_client

    policy, created = service.get_or_create_access_policy(
        "domain-1", "hydra-vftd-BPR-2-AC", {"defaultAction": {"action": "BLOCK"}}
    )

    assert created is True
    assert policy.uid == "policy-2"
    assert api_client.call_api.call_count == 2


def test_clone_access_policy_submits_polls_and_finds_by_name() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("POST", "https://example.test", {}, None, [])
    api_client.call_api.side_effect = [
        _mock_api_response(
            {
                "policies": [
                    {
                        "id": "source-policy-1",
                        "type": "AccessPolicy",
                        "cloneName": "hydra-vftd-BPR-4-AC-BPR-2-4-5",
                        "metadata": {"task": {"id": "task-1"}},
                    }
                ]
            }
        ),
        _mock_api_response({"status": "SUCCESS"}),
        _mock_api_response(
            {"items": [{"id": "clone-policy-1", "name": "hydra-vftd-BPR-4-AC-BPR-2-4-5"}]}
        ),
    ]
    service = CdfmcAccessPolicyService.__new__(CdfmcAccessPolicyService)
    service._api_client = api_client

    with patch(
        "cisco_sccfm_core.services.inventory.cdfmc_access_policy_service.time.sleep"
    ) as mock_sleep:
        policy = service.clone_access_policy(
            "domain-1", "source-policy-1", "hydra-vftd-BPR-4-AC-BPR-2-4-5"
        )

    assert policy.uid == "clone-policy-1"
    assert policy.name == "hydra-vftd-BPR-4-AC-BPR-2-4-5"
    mock_sleep.assert_not_called()
    submit_body = api_client.param_serialize.call_args_list[0].kwargs["body"]
    assert submit_body == {
        "policies": [
            {
                "id": "source-policy-1",
                "type": "AccessPolicy",
                "cloneName": "hydra-vftd-BPR-4-AC-BPR-2-4-5",
            }
        ]
    }


def test_clone_access_policy_raises_when_task_fails() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("POST", "https://example.test", {}, None, [])
    api_client.call_api.side_effect = [
        _mock_api_response(
            {
                "policies": [
                    {"id": "source-policy-1", "metadata": {"task": {"id": "task-1"}}}
                ]
            }
        ),
        _mock_api_response({"status": "FAILED", "message": "boom"}),
    ]
    service = CdfmcAccessPolicyService.__new__(CdfmcAccessPolicyService)
    service._api_client = api_client

    with pytest.raises(RuntimeError, match="boom"):
        service.clone_access_policy("domain-1", "source-policy-1", "new-clone")


def test_clone_access_policy_raises_on_timeout() -> None:
    api_client = Mock()
    api_client.param_serialize.return_value = ("POST", "https://example.test", {}, None, [])
    api_client.call_api.side_effect = [
        _mock_api_response(
            {
                "policies": [
                    {"id": "source-policy-1", "metadata": {"task": {"id": "task-1"}}}
                ]
            }
        ),
        _mock_api_response({"status": "RUNNING"}),
        _mock_api_response({"status": "RUNNING"}),
    ]
    service = CdfmcAccessPolicyService.__new__(CdfmcAccessPolicyService)
    service._api_client = api_client

    with patch(
        "cisco_sccfm_core.services.inventory.cdfmc_access_policy_service.time.time",
        side_effect=[0, 0, 100],
    ):
        with patch(
            "cisco_sccfm_core.services.inventory.cdfmc_access_policy_service.time.sleep"
        ):
            with pytest.raises(TimeoutError):
                service.clone_access_policy(
                    "domain-1",
                    "source-policy-1",
                    "new-clone",
                    polling_interval_sec=0,
                    timeout_sec=10,
                )

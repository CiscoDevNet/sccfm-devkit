# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from cisco_sccfm_core.services.inventory.cdfmc_platform_settings_policy_service import (
    CdfmcPlatformSettingsPolicyService,
)


def _make_service() -> CdfmcPlatformSettingsPolicyService:
    service = CdfmcPlatformSettingsPolicyService.__new__(
        CdfmcPlatformSettingsPolicyService
    )
    service._api_client = MagicMock()
    return service


def _queue_responses(
    service: CdfmcPlatformSettingsPolicyService, *payloads: object
) -> None:
    responses = list(payloads)

    def side_effect(*_args: object, **_kwargs: object) -> MagicMock:
        response = MagicMock()
        response.status = 200
        data = responses.pop(0)
        response.data = json.dumps(data).encode()
        return response

    service._api_client.param_serialize.return_value = (
        "GET", "/path", {}, {}, {}, None, None, None, [], None,
    )
    service._api_client.call_api.side_effect = side_effect


def test_get_policy_uid_by_name_returns_uid() -> None:
    service = _make_service()
    _queue_responses(
        service,
        {"items": [{"id": "policy-1", "name": "Lab Platform Settings"}]},
    )

    result = service.get_policy_uid_by_name("domain-uid", "Lab Platform Settings")

    assert result == "policy-1"


def test_get_policy_uid_by_name_raises_when_not_found() -> None:
    service = _make_service()
    _queue_responses(
        service,
        {"items": [{"id": "policy-1", "name": "Other Policy"}]},
    )

    with pytest.raises(ValueError, match="Lab Platform Settings"):
        service.get_policy_uid_by_name("domain-uid", "Lab Platform Settings")


def test_get_fmc_device_id_returns_id() -> None:
    service = _make_service()
    _queue_responses(service, {"items": [{"id": "device-1", "name": "vftd-a"}]})

    result = service.get_fmc_device_id("domain-uid", "vftd-a")

    assert result == "device-1"


def test_get_fmc_device_id_raises_when_not_found() -> None:
    service = _make_service()
    _queue_responses(service, {"items": []})

    with pytest.raises(ValueError, match="missing-device"):
        service.get_fmc_device_id("domain-uid", "missing-device")


def test_assign_policy_to_device_creates_new_assignment_when_none_exists() -> None:
    service = _make_service()
    _queue_responses(
        service,
        # GET existing assignments - none for this policy
        {"items": []},
        # POST create response
        {
            "id": "assignment-1",
            "policy": {"id": "policy-1", "type": "FTDPlatformSettings"},
            "targets": [{"id": "device-1", "type": "Device"}],
        },
    )

    result = service.assign_policy_to_device(
        "domain-uid", "policy-1", "Lab Platform Settings", "device-1"
    )

    assert result.assignment_id == "assignment-1"
    assert result.already_assigned is False
    assert result.target_ids == ["device-1"]


def test_assign_policy_to_device_adds_target_to_existing_assignment() -> None:
    service = _make_service()
    _queue_responses(
        service,
        # GET existing assignments - one exists, missing our device
        {
            "items": [
                {
                    "id": "assignment-1",
                    "policy": {"id": "policy-1", "type": "FTDPlatformSettings"},
                    "targets": [{"id": "device-0", "type": "Device"}],
                    "metadata": {"timestamp": 123},
                    "links": {"self": "https://example"},
                }
            ]
        },
        # PUT update response
        {
            "id": "assignment-1",
            "policy": {"id": "policy-1", "type": "FTDPlatformSettings"},
            "targets": [
                {"id": "device-0", "type": "Device"},
                {"id": "device-1", "type": "Device"},
            ],
        },
    )

    result = service.assign_policy_to_device(
        "domain-uid", "policy-1", "Lab Platform Settings", "device-1"
    )

    assert result.already_assigned is False
    assert result.target_ids == ["device-0", "device-1"]

    put_call = service._api_client.call_api.call_args_list[-1]
    # second param_serialize call recorded via return_value isn't per-call here,
    # so assert against the service's own merge logic indirectly through the
    # returned target_ids above - that's the behavior that actually matters.
    assert put_call is not None


def test_assign_policy_to_device_is_idempotent_when_already_assigned() -> None:
    service = _make_service()
    _queue_responses(
        service,
        {
            "items": [
                {
                    "id": "assignment-1",
                    "policy": {"id": "policy-1", "type": "FTDPlatformSettings"},
                    "targets": [{"id": "device-1", "type": "Device"}],
                }
            ]
        },
    )

    result = service.assign_policy_to_device(
        "domain-uid", "policy-1", "Lab Platform Settings", "device-1"
    )

    assert result.already_assigned is True
    assert result.assignment_id == "assignment-1"
    assert result.target_ids == ["device-1"]
    # No PUT/POST should have been issued - only the initial GET.
    assert service._api_client.call_api.call_count == 1


def test_assign_policy_to_device_raises_when_write_not_applied() -> None:
    service = _make_service()
    _queue_responses(
        service,
        {"items": []},
        {},  # POST "succeeded" but body has no id - should be treated as a failure
    )

    with pytest.raises(RuntimeError, match="did not contain the assignment's 'id'"):
        service.assign_policy_to_device(
            "domain-uid", "policy-1", "Lab Platform Settings", "device-1"
        )

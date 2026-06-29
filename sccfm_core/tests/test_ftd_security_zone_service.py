# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from unittest.mock import MagicMock

from sccfm_core.services.inventory.ftd_security_zone_service import (
    FtdSecurityZoneService,
    SecurityZone,
)


def _make_service() -> FtdSecurityZoneService:
    service = FtdSecurityZoneService.__new__(FtdSecurityZoneService)
    service._api_client = MagicMock()
    return service


def _mock_response(service: FtdSecurityZoneService, data: object) -> None:
    response = MagicMock()
    response.data = json.dumps(data).encode()
    service._api_client.param_serialize.return_value = ("GET", "/path", {}, {}, {}, None, None, None, [], None)
    service._api_client.call_api.return_value = response


def test_list_security_zones_returns_zones() -> None:
    service = _make_service()
    _mock_response(service, {
        "items": [
            {"id": "zone-1", "name": "inside-zone", "interfaceMode": "ROUTED"},
            {"id": "zone-2", "name": "outside-zone", "interfaceMode": "ROUTED"},
        ]
    })

    result = service.list_security_zones("domain-uid")

    assert len(result) == 2
    assert result[0].name == "inside-zone"
    assert result[0].id == "zone-1"


def test_create_security_zone_returns_new_zone() -> None:
    service = _make_service()
    _mock_response(service, {"id": "zone-3", "name": "dmz-zone", "interfaceMode": "ROUTED"})

    result = service.create_security_zone("domain-uid", "dmz-zone")

    assert result.id == "zone-3"
    assert result.name == "dmz-zone"
    assert result.interface_mode == "ROUTED"


def test_get_or_create_returns_existing_without_creating() -> None:
    service = _make_service()

    responses = [
        {"items": [{"id": "zone-1", "name": "inside-zone", "interfaceMode": "ROUTED"}]},
    ]
    idx = 0

    def side_effect(*_args: object, **_kwargs: object) -> MagicMock:
        nonlocal idx
        response = MagicMock()
        response.data = json.dumps(responses[idx]).encode()
        idx += 1
        return response

    service._api_client.param_serialize.return_value = ("GET", "/path", {}, {}, {}, None, None, None, [], None)
    service._api_client.call_api.side_effect = side_effect

    result = service.get_or_create_security_zone("domain-uid", "inside-zone")

    assert result.id == "zone-1"
    assert service._api_client.call_api.call_count == 1


def test_get_or_create_creates_when_not_found() -> None:
    service = _make_service()

    responses = [
        {"items": []},
        {"id": "zone-new", "name": "new-zone", "interfaceMode": "ROUTED"},
    ]
    idx = 0

    def side_effect(*_args: object, **_kwargs: object) -> MagicMock:
        nonlocal idx
        response = MagicMock()
        response.data = json.dumps(responses[idx]).encode()
        idx += 1
        return response

    service._api_client.param_serialize.return_value = ("POST", "/path", {}, {}, {}, None, None, None, [], None)
    service._api_client.call_api.side_effect = side_effect

    result = service.get_or_create_security_zone("domain-uid", "new-zone")

    assert result.id == "zone-new"
    assert service._api_client.call_api.call_count == 2

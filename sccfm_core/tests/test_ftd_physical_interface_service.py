# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from sccfm_core.services.inventory.ftd_physical_interface_service import (
    FtdPhysicalInterface,
    FtdPhysicalInterfaceService,
    Ipv4Config,
)


def _make_service() -> FtdPhysicalInterfaceService:
    service = FtdPhysicalInterfaceService.__new__(FtdPhysicalInterfaceService)
    service._api_client = MagicMock()
    return service


def _mock_response(service: FtdPhysicalInterfaceService, data: object) -> None:
    response = MagicMock()
    response.data = json.dumps(data).encode()
    service._api_client.param_serialize.return_value = ("GET", "/path", {}, {}, {}, None, None, None, [], None)
    service._api_client.call_api.return_value = response


def test_get_fmc_device_id_returns_id() -> None:
    service = _make_service()
    _mock_response(service, {"items": [{"id": "fmc-device-123", "name": "vftd-a"}]})

    result = service.get_fmc_device_id("domain-uid", "vftd-a")

    assert result == "fmc-device-123"


def test_get_fmc_device_id_raises_when_not_found() -> None:
    service = _make_service()
    _mock_response(service, {"items": []})

    try:
        service.get_fmc_device_id("domain-uid", "missing-device")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "missing-device" in str(e)


def test_list_interfaces_returns_interfaces() -> None:
    service = _make_service()
    _mock_response(service, {
        "items": [
            {"id": "iface-1", "name": "GigabitEthernet0/0", "ifname": "", "enabled": False},
            {"id": "iface-2", "name": "GigabitEthernet0/1", "ifname": "inside", "enabled": True},
        ]
    })

    result = service.list_interfaces("domain-uid", "device-id")

    assert len(result) == 2
    assert result[1].ifname == "inside"


def test_configure_interface_updates_nameif_and_ip() -> None:
    service = _make_service()

    existing_raw = {"id": "iface-2", "name": "GigabitEthernet0/1", "ifname": "", "enabled": False, "type": "PhysicalInterface"}
    updated_raw = {**existing_raw, "ifname": "inside", "enabled": True, "ipv4": {"static": {"address": "11.11.11.10", "netmask": "255.255.255.0"}}}

    responses = [
        {"items": [existing_raw]},
        updated_raw,
    ]
    idx = 0

    def side_effect(*_args: object, **_kwargs: object) -> MagicMock:
        nonlocal idx
        response = MagicMock()
        response.data = json.dumps(responses[idx]).encode()
        idx += 1
        return response

    service._api_client.param_serialize.return_value = ("PUT", "/path", {}, {}, {}, None, None, None, [], None)
    service._api_client.call_api.side_effect = side_effect

    result = service.configure_interface(
        "domain-uid",
        "device-id",
        "GigabitEthernet0/1",
        nameif="inside",
        ipv4=Ipv4Config(address="11.11.11.10", netmask="255.255.255.0"),
        enabled=True,
    )

    assert result.ifname == "inside"
    assert result.enabled is True


def test_configure_interface_raises_when_interface_not_found() -> None:
    service = _make_service()
    _mock_response(service, {"items": [{"id": "iface-1", "name": "GigabitEthernet0/0", "ifname": "", "enabled": False}]})

    try:
        service.configure_interface(
            "domain-uid", "device-id", "GigabitEthernet0/99", nameif="dmz"
        )
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "GigabitEthernet0/99" in str(e)

from __future__ import annotations

from typing import Any

import click
import pytest
from _pytest.monkeypatch import MonkeyPatch
from rich.console import Console
from scc_firewall_manager_sdk import Device, DevicePage

from sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceFilters,
    AsaDeviceTargetCommand,
    asa_device_filter_params,
)
from sccfm_core import InventoryService


class _DummyAsaTargetCommand(AsaDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "dummy-asa-target"

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        raise NotImplementedError


def test_asa_device_filter_params_include_device_name() -> None:
    params = asa_device_filter_params(include_device_name=True, query_help_text="query help")
    option_names = [p.name for p in params if isinstance(p, click.Option)]
    assert option_names == ["device_name", "query", "limit", "offset", "device_uids"]


def test_asa_device_filter_params_without_device_name() -> None:
    params = asa_device_filter_params(include_device_name=False, query_help_text="query help")
    option_names = [p.name for p in params if isinstance(p, click.Option)]
    assert option_names == ["query", "limit", "offset", "device_uids"]


def test_validate_filters_requires_one_selector() -> None:
    command = _DummyAsaTargetCommand(Console())
    ctx = click.Context(click.Command("dummy"))
    with pytest.raises(click.UsageError, match="Provide one of: --query or --device-uids."):
        command._validate_asa_device_filters(
            ctx=ctx,
            filters=AsaDeviceFilters(
                device_name=None,
                query=None,
                device_uids=None,
                limit=50,
                offset=0,
            ),
            include_device_name=False,
        )


def test_validate_filters_exactly_one_selector() -> None:
    command = _DummyAsaTargetCommand(Console())
    ctx = click.Context(click.Command("dummy"))
    with pytest.raises(click.UsageError, match="Provide exactly one of --query or --device-uids."):
        command._validate_asa_device_filters(
            ctx=ctx,
            filters=AsaDeviceFilters(
                device_name=None,
                query="name:test-*",
                device_uids=("uid-1",),
                limit=50,
                offset=0,
            ),
            include_device_name=False,
            require_exactly_one=True,
        )


def test_resolve_asa_targets_uses_device_name_and_wraps_query(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _stub_init(self: InventoryService, config: Any) -> None:
        return None

    def _fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured["limit"] = limit
        captured["offset"] = offset
        captured["query"] = query
        return DevicePage(
            count=1,
            items=[Device(uid="uid-1", name="asa-1", deviceType="ASA")],
        )

    monkeypatch.setattr(InventoryService, "__init__", _stub_init)
    monkeypatch.setattr(InventoryService, "get_devices", _fake_get_devices)

    command = _DummyAsaTargetCommand(Console())
    ctx = click.Context(click.Command("dummy"))
    targets = command.resolve_asa_targets_from_kwargs(
        ctx=ctx,
        kwargs={
            "device_name": "branch-*",
            "query": None,
            "device_uids": None,
            "limit": 10,
            "offset": 5,
        },
        config=object(),
        include_device_name=True,
        wrap_query_with_parentheses=True,
    )

    assert captured["limit"] == 10
    assert captured["offset"] == 5
    assert captured["query"] == "(name:branch-*) AND deviceType:ASA"
    assert targets.device_uids == ["uid-1"]
    assert targets.uid_to_device["uid-1"].name == "asa-1"


def test_resolve_asa_targets_builds_uid_query(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _stub_init(self: InventoryService, config: Any) -> None:
        return None

    def _fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured["query"] = query
        return DevicePage(
            count=2,
            items=[
                Device(uid="uid-1", name="asa-1", deviceType="ASA"),
                Device(uid="uid-2", name="asa-2", deviceType="ASA"),
            ],
        )

    monkeypatch.setattr(InventoryService, "__init__", _stub_init)
    monkeypatch.setattr(InventoryService, "get_devices", _fake_get_devices)

    command = _DummyAsaTargetCommand(Console())
    ctx = click.Context(click.Command("dummy"))
    targets = command.resolve_asa_targets_from_kwargs(
        ctx=ctx,
        kwargs={
            "query": None,
            "device_uids": ("uid-1", "uid-2"),
            "limit": 50,
            "offset": 0,
        },
        config=object(),
        include_device_name=False,
    )

    assert captured["query"] == "uid:uid-1 OR uid:uid-2"
    assert targets.device_uids == ["uid-1", "uid-2"]

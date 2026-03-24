from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import list_asa_not_on_version  # noqa: E402
from scc_firewall_manager_sdk import (
    ApiException,
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)

_TARGET_VERSION = "9.20(3)13"


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def device_on_target() -> Device:
    return Device(
        uid="uid-1",
        name="up-to-date-asa",
        deviceType=EntityType.ASA,
        softwareVersion=_TARGET_VERSION,
        asdmVersion="7.20(1)",
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def device_off_target() -> Device:
    return Device(
        uid="uid-2",
        name="needs-upgrade-asa",
        deviceType=EntityType.ASA,
        softwareVersion="9.18.4",
        asdmVersion="7.18(1)",
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def base_params() -> dict[str, Any]:
    return {
        "version": _TARGET_VERSION,
        "query": None,
        "uids": None,
        "limit": 50,
        "offset": 0,
        "region": "us",
        "api_token": "test-token-123",
    }


def _mock_module(params: dict[str, Any]) -> MagicMock:
    mock = MagicMock()
    mock.params = params.copy()
    mock.check_mode = False
    mock.exit_json.side_effect = SystemExit(0)
    mock.fail_json.side_effect = SystemExit(1)
    return mock


# ── Query-based device fetch ──────────────────────────────────────


@patch("plugins.modules.list_asa_not_on_version.create_config")
@patch("plugins.modules.list_asa_not_on_version.InventoryService")
@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_returns_devices_not_on_version(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
    device_on_target: Device,
    device_off_target: Device,
) -> None:
    """Devices on the target version are excluded; only off-version devices returned."""
    params = {**base_params, "query": "name:prod-*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(
        count=2, limit=50, offset=0, items=[device_on_target, device_off_target]
    )
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_asa_not_on_version.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is False
    assert kw["device_count"] == 1
    assert kw["matched_device_count"] == 2
    assert len(kw["devices"]) == 1
    assert kw["devices"][0]["uid"] == "uid-2"
    assert kw["devices"][0]["software_version"] == "9.18.4"


@patch("plugins.modules.list_asa_not_on_version.create_config")
@patch("plugins.modules.list_asa_not_on_version.InventoryService")
@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_all_devices_on_version_returns_empty(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
    device_on_target: Device,
) -> None:
    """When all devices are on the target version, returns empty list and count=0."""
    params = {**base_params, "query": "name:prod-*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[device_on_target]
    )
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_asa_not_on_version.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["device_count"] == 0
    assert kw["matched_device_count"] == 1
    assert kw["devices"] == []
    assert f"All 1 matched device(s) are on version {_TARGET_VERSION}" in kw["msg"]


@patch("plugins.modules.list_asa_not_on_version.create_config")
@patch("plugins.modules.list_asa_not_on_version.InventoryService")
@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_no_devices_match_filter_returns_distinct_message(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
) -> None:
    """No matched devices should not be reported as all devices being compliant."""
    params = {**base_params, "query": "name:missing-*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=0, limit=50, offset=0, items=[])
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_asa_not_on_version.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["devices"] == []
    assert kw["device_count"] == 0
    assert kw["matched_device_count"] == 0
    assert kw["msg"] == "No ASA devices matched the specified filter."


# ── Query construction ────────────────────────────────────────────


@patch("plugins.modules.list_asa_not_on_version.create_config")
@patch("plugins.modules.list_asa_not_on_version.InventoryService")
@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_query_combines_with_asa_device_type(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
) -> None:
    """User query is wrapped and combined with deviceType:ASA."""
    params = {**base_params, "query": "name:branch-*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=0, items=[])
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_asa_not_on_version.run_module()

    call_kwargs = mock_inv.get_devices.call_args[1]
    assert "(name:branch-*)" in call_kwargs["query"]
    assert "deviceType:ASA" in call_kwargs["query"]


@patch("plugins.modules.list_asa_not_on_version.create_config")
@patch("plugins.modules.list_asa_not_on_version.InventoryService")
@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_no_filter_queries_all_asa_devices(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
) -> None:
    """When no query or uids are provided, deviceType:ASA query is used."""
    mock_module = _mock_module(base_params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=0, items=[])
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_asa_not_on_version.run_module()

    call_kwargs = mock_inv.get_devices.call_args[1]
    assert call_kwargs["query"] == "deviceType:ASA"


# ── UID-based fetch ───────────────────────────────────────────────


@patch("plugins.modules.list_asa_not_on_version.create_config")
@patch("plugins.modules.list_asa_not_on_version.InventoryService")
@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_uids_builds_uid_query(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
    device_off_target: Device,
) -> None:
    """When uids are provided, inventory is queried via uid:... OR uid:... syntax."""
    params = {**base_params, "uids": ["uid-2", "uid-3"]}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=1, items=[device_off_target])
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_asa_not_on_version.run_module()

    call_kwargs = mock_inv.get_devices.call_args[1]
    assert "uid:uid-2" in call_kwargs["query"]
    assert "uid:uid-3" in call_kwargs["query"]


# ── Output structure ──────────────────────────────────────────────


@patch("plugins.modules.list_asa_not_on_version.create_config")
@patch("plugins.modules.list_asa_not_on_version.InventoryService")
@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_device_fields_are_serialized(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
    device_off_target: Device,
) -> None:
    """Device dicts contain all expected fields."""
    params = {**base_params, "query": "name:*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=1, items=[device_off_target])
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_asa_not_on_version.run_module()

    kw = mock_module.exit_json.call_args[1]
    device = kw["devices"][0]
    assert device["uid"] == "uid-2"
    assert device["name"] == "needs-upgrade-asa"
    assert device["software_version"] == "9.18.4"
    assert device["asdm_version"] == "7.18(1)"
    assert device["connectivity_state"] == "ONLINE"
    assert device["config_state"] == "SYNCED"


# ── Pagination ────────────────────────────────────────────────────


@patch("plugins.modules.list_asa_not_on_version.create_config")
@patch("plugins.modules.list_asa_not_on_version.InventoryService")
@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_limit_and_offset_are_forwarded(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
) -> None:
    """limit and offset params are forwarded to the inventory service."""
    params = {**base_params, "query": "name:*", "limit": 25, "offset": 10}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=0, items=[])
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_asa_not_on_version.run_module()

    call_kwargs = mock_inv.get_devices.call_args[1]
    assert call_kwargs["limit"] == 25
    assert call_kwargs["offset"] == 10


# ── Validation ────────────────────────────────────────────────────


@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_rejects_invalid_version_format(
    mock_ansible_cls: MagicMock,
    base_params: dict[str, Any],
) -> None:
    """A version string not matching the Cisco format causes fail_json."""
    params = {**base_params, "version": "not-a-version"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    with pytest.raises(SystemExit):
        list_asa_not_on_version.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "Invalid version format" in kw["msg"]


# ── Error handling ────────────────────────────────────────────────


@patch("plugins.modules.list_asa_not_on_version.create_config")
@patch("plugins.modules.list_asa_not_on_version.InventoryService")
@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_fails_on_unexpected_exception(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
) -> None:
    """Unexpected exceptions are caught and reported via fail_json."""
    params = {**base_params, "query": "name:*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.side_effect = Exception("Connection timeout")
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_asa_not_on_version.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "Connection timeout" in kw["msg"]


@patch("plugins.modules.list_asa_not_on_version.create_config")
@patch("plugins.modules.list_asa_not_on_version.InventoryService")
@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_fails_on_api_exception(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
) -> None:
    """ApiException is caught and reported with structured error fields."""
    params = {**base_params, "query": "name:*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    api_error = ApiException(status=403, reason="Forbidden")
    api_error.body = (
        '{"errorMsg": "Access denied", "errorCode": "FORBIDDEN", "details": {}}'
    )
    mock_inv = MagicMock()
    mock_inv.get_devices.side_effect = api_error
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_asa_not_on_version.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert kw["msg"] == "Access denied"
    assert kw["error_code"] == "FORBIDDEN"
    assert kw["status_code"] == 403


# ── Idempotency ───────────────────────────────────────────────────


@patch("plugins.modules.list_asa_not_on_version.create_config")
@patch("plugins.modules.list_asa_not_on_version.InventoryService")
@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_idempotent_returns_same_result_on_repeated_calls(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
    device_on_target: Device,
    device_off_target: Device,
) -> None:
    """Running the module twice with the same data produces identical results."""
    params = {**base_params, "query": "name:prod-*"}
    page = DevicePage(
        count=2, limit=50, offset=0, items=[device_on_target, device_off_target]
    )

    results: list[dict[str, Any]] = []
    for _ in range(2):
        mock_module = _mock_module(params)
        mock_ansible_cls.return_value = mock_module

        mock_inv = MagicMock()
        mock_inv.get_devices.return_value = page
        mock_inventory_cls.return_value = mock_inv

        with pytest.raises(SystemExit):
            list_asa_not_on_version.run_module()

        mock_module.exit_json.assert_called_once()
        results.append(mock_module.exit_json.call_args[1])

    assert results[0]["changed"] is False
    assert results[1]["changed"] is False
    assert results[0]["devices"] == results[1]["devices"]
    assert results[0]["device_count"] == results[1]["device_count"]
    assert results[0]["matched_device_count"] == results[1]["matched_device_count"]


@patch("plugins.modules.list_asa_not_on_version.create_config")
@patch("plugins.modules.list_asa_not_on_version.InventoryService")
@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_never_reports_changed(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
    device_off_target: Device,
) -> None:
    """A read-only module must always return changed=False."""
    params = {**base_params, "query": "name:*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=1, items=[device_off_target])
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_asa_not_on_version.run_module()

    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is False


# ── Auth validation ───────────────────────────────────────────────


@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_fails_if_region_not_provided(
    mock_ansible_cls: MagicMock,
    base_params: dict[str, Any],
) -> None:
    """fail_json is called when region is absent and not in env."""
    params = {**base_params}
    del params["region"]
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            list_asa_not_on_version.run_module()

    mock_module.fail_json.assert_called_once()
    assert "region is required" in mock_module.fail_json.call_args[1]["msg"]


@patch("plugins.modules.list_asa_not_on_version.AnsibleModule")
def test_fails_if_api_token_not_provided(
    mock_ansible_cls: MagicMock,
    base_params: dict[str, Any],
) -> None:
    """fail_json is called when api_token is absent and not in env."""
    params = {**base_params}
    del params["api_token"]
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            list_asa_not_on_version.run_module()

    mock_module.fail_json.assert_called_once()
    assert "api_token is required" in mock_module.fail_json.call_args[1]["msg"]

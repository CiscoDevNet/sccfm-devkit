"""Tests for sccfm_core.services.inventory.asa_ha_check_service module."""

from __future__ import annotations

from types import SimpleNamespace

from sccfm_core.models.asa_failover_status import (
    AsaFailoverInterface,
    AsaFailoverStatus,
    AsaFailoverUnit,
    HaCheckResult,
)
from sccfm_core.services.inventory.asa_ha_check_service import (
    AsaHaCheckService,
    InterfaceLookupResult,
    UnmonitoredInterface,
    _check_config_synced,
    _check_failover_enabled,
    _check_interfaces_healthy,
    _check_lan_link,
    _check_mate_ready,
    _check_unmonitored,
    _check_version_match,
    _is_unmonitored,
    _run_checks,
)


def _make_status(
    *,
    failover_enabled: bool = True,
    lan_state: str = "up",
    lan_hardware: str = "GigabitEthernet0/8",
    version_ours: str = "9.20(3)10",
    version_mate: str = "9.20(3)10",
    this_host_state: str = "Active",
    other_host_state: str = "Standby Ready",
    this_interfaces: list[AsaFailoverInterface] | None = None,
    other_interfaces: list[AsaFailoverInterface] | None = None,
    monitored_count: int = 3,
    config_sync_state: str = "Sync Done",
) -> AsaFailoverStatus:
    """Helper to build a test AsaFailoverStatus with sensible defaults."""
    if this_interfaces is None:
        this_interfaces = [
            AsaFailoverInterface(
                name="outside", ip_address="10.0.0.1", status="Normal", monitoring="Monitored"
            ),
            AsaFailoverInterface(
                name="inside", ip_address="192.168.1.1", status="Normal", monitoring="Monitored"
            ),
            AsaFailoverInterface(
                name="management", ip_address="10.0.1.1", status="Normal", monitoring="Monitored"
            ),
        ]
    if other_interfaces is None:
        other_interfaces = [
            AsaFailoverInterface(
                name="outside", ip_address="10.0.0.2", status="Normal", monitoring="Monitored"
            ),
            AsaFailoverInterface(
                name="inside", ip_address="192.168.1.2", status="Normal", monitoring="Monitored"
            ),
            AsaFailoverInterface(
                name="management", ip_address="10.0.1.2", status="Normal", monitoring="Monitored"
            ),
        ]
    return AsaFailoverStatus(
        failover_enabled=failover_enabled,
        failover_unit="Primary",
        lan_interface_name="INTFC",
        lan_hardware=lan_hardware,
        lan_state=lan_state,
        version_ours=version_ours,
        version_mate=version_mate,
        serial_ours="JAD251400QT",
        serial_mate="9AA77409PDA",
        last_failover="14:23:15 UTC Jun 5 2024",
        monitored_count=monitored_count,
        monitored_max=110,
        this_host=AsaFailoverUnit(
            role="Primary",
            state=this_host_state,
            active_time=12345,
            interfaces=this_interfaces,
        ),
        other_host=AsaFailoverUnit(
            role="Secondary",
            state=other_host_state,
            active_time=0,
            interfaces=other_interfaces,
        ),
        config_sync_state=config_sync_state,
    )


class TestCheckFailoverEnabled:
    def test_should_pass_when_enabled(self) -> None:
        result = _check_failover_enabled(_make_status(failover_enabled=True))
        assert result.passed is True
        assert result.name == "failover_enabled"

    def test_should_fail_when_disabled(self) -> None:
        result = _check_failover_enabled(_make_status(failover_enabled=False))
        assert result.passed is False
        assert "OFF" in result.detail


class TestCheckLanLink:
    def test_should_pass_when_up(self) -> None:
        result = _check_lan_link(_make_status(lan_state="up"))
        assert result.passed is True

    def test_should_fail_when_down(self) -> None:
        result = _check_lan_link(_make_status(lan_state="down"))
        assert result.passed is False
        assert "down" in result.detail


class TestCheckVersionMatch:
    def test_should_pass_when_match(self) -> None:
        result = _check_version_match(
            _make_status(version_ours="9.20(3)10", version_mate="9.20(3)10")
        )
        assert result.passed is True

    def test_should_fail_when_mismatch(self) -> None:
        result = _check_version_match(
            _make_status(version_ours="9.20(3)10", version_mate="9.18(4)5")
        )
        assert result.passed is False
        assert "9.18(4)5" in result.detail


class TestCheckMateReady:
    def test_should_pass_when_standby_ready(self) -> None:
        result = _check_mate_ready(_make_status(other_host_state="Standby Ready"))
        assert result.passed is True

    def test_should_pass_when_this_host_is_standby_ready(self) -> None:
        result = _check_mate_ready(
            _make_status(
                this_host_state="Standby Ready",
                other_host_state="Active",
            )
        )
        assert result.passed is True

    def test_should_fail_when_failed(self) -> None:
        result = _check_mate_ready(_make_status(other_host_state="Failed"))
        assert result.passed is False
        assert "Failed" in result.detail

    def test_should_fail_when_cold_standby(self) -> None:
        result = _check_mate_ready(_make_status(other_host_state="Cold Standby"))
        assert result.passed is False


class TestCheckInterfacesHealthy:
    def test_should_pass_when_all_normal(self) -> None:
        result = _check_interfaces_healthy(_make_status())
        assert result.passed is True

    def test_should_fail_when_this_host_interface_failed(self) -> None:
        ifaces = [
            AsaFailoverInterface(
                name="outside", ip_address="10.0.0.1", status="Normal", monitoring="Monitored"
            ),
            AsaFailoverInterface(
                name="inside", ip_address="192.168.1.1", status="Failed", monitoring="Monitored"
            ),
        ]
        result = _check_interfaces_healthy(_make_status(this_interfaces=ifaces))
        assert result.passed is False
        assert "inside=Failed" in result.detail

    def test_should_fail_when_mate_interface_failed(self) -> None:
        other_ifaces = [
            AsaFailoverInterface(
                name="outside", ip_address="10.0.0.2", status="Failed", monitoring="Monitored"
            ),
        ]
        result = _check_interfaces_healthy(_make_status(other_interfaces=other_ifaces))
        assert result.passed is False
        assert "outside(mate)=Failed" in result.detail

    def test_should_ignore_non_monitored_interfaces(self) -> None:
        ifaces = [
            AsaFailoverInterface(
                name="outside", ip_address="10.0.0.1", status="Normal", monitoring="Monitored"
            ),
            AsaFailoverInterface(
                name="diagnostic", ip_address="0.0.0.0", status="Normal", monitoring="Waiting"
            ),
        ]
        result = _check_interfaces_healthy(_make_status(this_interfaces=ifaces))
        assert result.passed is True


class TestCheckConfigSynced:
    def test_should_pass_when_sync_done(self) -> None:
        result = _check_config_synced(_make_status(config_sync_state="Sync Done"))
        assert result.passed is True

    def test_should_fail_when_skipped(self) -> None:
        result = _check_config_synced(_make_status(config_sync_state="Sync Skipped - STANDBY"))
        assert result.passed is False

    def test_should_pass_when_unknown(self) -> None:
        result = _check_config_synced(_make_status(config_sync_state="unknown"))
        assert result.passed is True


class TestCheckUnmonitored:
    def test_should_pass_when_none(self) -> None:
        result = _check_unmonitored(InterfaceLookupResult())
        assert result.passed is True

    def test_should_fail_when_present(self) -> None:
        result = _check_unmonitored(
            InterfaceLookupResult(
                unmonitored_interfaces=[
                    UnmonitoredInterface(hardware_name="GigabitEthernet0/3", name="dmz"),
                ]
            )
        )
        assert result.passed is False
        assert "dmz" in result.detail

    def test_should_list_multiple(self) -> None:
        result = _check_unmonitored(
            InterfaceLookupResult(
                unmonitored_interfaces=[
                    UnmonitoredInterface(hardware_name="GigabitEthernet0/3", name="dmz"),
                    UnmonitoredInterface(
                        hardware_name="GigabitEthernet0/4",
                        name="extranet",
                    ),
                ]
            )
        )
        assert result.passed is False
        assert "dmz" in result.detail
        assert "extranet" in result.detail

    def test_should_fail_when_interface_lookup_errors_occur(self) -> None:
        result = _check_unmonitored(
            InterfaceLookupResult(errors=["physical interfaces: unauthorized"])
        )
        assert result.passed is False
        assert "Unable to verify interface monitoring" in result.detail
        assert "unauthorized" in result.detail


class TestIsUnmonitored:
    def test_should_flag_enabled_named_unmonitored(self) -> None:
        iface = _mock_interface(enabled=True, name="dmz", monitor_interface=False)
        assert _is_unmonitored(iface) is True

    def test_should_skip_disabled(self) -> None:
        iface = _mock_interface(enabled=False, name="dmz", monitor_interface=False)
        assert _is_unmonitored(iface) is False

    def test_should_skip_unnamed(self) -> None:
        iface = _mock_interface(enabled=True, name="", monitor_interface=False)
        assert _is_unmonitored(iface) is False

    def test_should_skip_monitored(self) -> None:
        iface = _mock_interface(enabled=True, name="outside", monitor_interface=True)
        assert _is_unmonitored(iface) is False


class TestRunChecks:
    def test_should_return_seven_checks(self) -> None:
        checks = _run_checks(_make_status(), InterfaceLookupResult())
        assert len(checks) == 7

    def test_all_pass_for_healthy_status(self) -> None:
        checks = _run_checks(_make_status(), InterfaceLookupResult())
        assert all(c.passed for c in checks)

    def test_should_return_ha_check_result_instances(self) -> None:
        checks = _run_checks(_make_status(), InterfaceLookupResult())
        assert all(isinstance(c, HaCheckResult) for c in checks)


class TestFindUnmonitoredInterfaces:
    def test_should_capture_interface_lookup_errors(self) -> None:
        service = AsaHaCheckService.__new__(AsaHaCheckService)
        service._interfaces_api = _FakeInterfacesApi(
            physical_error=RuntimeError("physical lookup failed"),
            subinterface_items=[
                _mock_interface(
                    enabled=True,
                    name="dmz",
                    monitor_interface=False,
                    hardware_name="GigabitEthernet0/3",
                )
            ],
        )

        result = service._find_unmonitored_interfaces("uid-1")

        assert result.errors == ["physical interfaces: physical lookup failed"]
        assert result.unmonitored_interfaces == [
            UnmonitoredInterface(hardware_name="GigabitEthernet0/3", name="dmz")
        ]


def _mock_interface(
    *,
    enabled: bool,
    name: str,
    monitor_interface: bool,
    hardware_name: str = "GigabitEthernet0/1",
) -> object:
    """Create a minimal mock of AsaInterface for _is_unmonitored tests."""

    class _FakeInterface:
        def __init__(self) -> None:
            self.enabled = enabled
            self.name = name
            self.monitor_interface = monitor_interface
            self.hardware_name = hardware_name

    return _FakeInterface()  # type: ignore[return-value]


class _FakeInterfacesApi:
    def __init__(
        self,
        *,
        physical_items: list[object] | None = None,
        subinterface_items: list[object] | None = None,
        physical_error: Exception | None = None,
        subinterface_error: Exception | None = None,
    ) -> None:
        self._physical_items = physical_items or []
        self._subinterface_items = subinterface_items or []
        self._physical_error = physical_error
        self._subinterface_error = subinterface_error

    def get_asa_physical_interfaces(self, *, device_uid: str, limit: str) -> SimpleNamespace:
        del device_uid, limit
        if self._physical_error is not None:
            raise self._physical_error
        return SimpleNamespace(items=self._physical_items)

    def get_asa_sub_interfaces(self, *, device_uid: str, limit: str) -> SimpleNamespace:
        del device_uid, limit
        if self._subinterface_error is not None:
            raise self._subinterface_error
        return SimpleNamespace(items=self._subinterface_items)

from __future__ import annotations

from scc_firewall_manager_sdk import (
    CdoTransaction,
    DeviceUpgradesApi,
    UpgradeFtdDeviceInput,
    UpgradeFtdDevicesInput,
)

from sccfm_core.factories import ApiClientFactory
from sccfm_core.types import ConfigLike
from sccfm_core.utils import validate_uids


class FtdUpgradeService:
    """Triggers FTD firmware upgrades for single or multiple devices."""

    def __init__(self, config: ConfigLike) -> None:
        self._upgrades_api = DeviceUpgradesApi(ApiClientFactory().build(config=config))

    def upgrade_single(
        self,
        *,
        device_uid: str,
        upgrade_package_uid: str,
        stage_upgrade: bool = False,
        ignore_maintenance_window: bool = False,
        name: str | None = None,
    ) -> CdoTransaction:
        """Trigger an upgrade on a single FTD device.

        Returns the :class:`CdoTransaction` tracking the async operation.
        """
        validate_uids([device_uid])
        upgrade_input = UpgradeFtdDeviceInput(
            upgradePackageUid=upgrade_package_uid,
            stageUpgrade=stage_upgrade,
            ignoreMaintenanceWindow=ignore_maintenance_window,
            name=name,
        )
        return self._upgrades_api.upgrade_ftd_device(
            device_uid=device_uid,
            upgrade_ftd_device_input=upgrade_input,
        )

    def upgrade_multiple(
        self,
        *,
        device_uids: list[str],
        upgrade_package_uid: str,
        stage_upgrade: bool = False,
        ignore_maintenance_window: bool = False,
        name: str | None = None,
    ) -> CdoTransaction:
        """Trigger an upgrade on multiple FTD devices (up to 50).

        Returns the :class:`CdoTransaction` tracking the async operation.
        """
        validate_uids(device_uids)
        upgrade_input = UpgradeFtdDevicesInput(
            deviceUids=device_uids,
            upgradePackageUid=upgrade_package_uid,
            stageUpgrade=stage_upgrade,
            ignoreMaintenanceWindow=ignore_maintenance_window,
            name=name,
        )
        return self._upgrades_api.upgrade_ftd_devices(
            upgrade_ftd_devices_input=upgrade_input,
        )

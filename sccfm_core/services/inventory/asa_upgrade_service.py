from __future__ import annotations

from scc_firewall_manager_sdk import (
    CdoTransaction,
    DeviceUpgradesApi,
    UpgradeAsaDeviceInput,
    UpgradeAsaDevicesInput,
)

from sccfm_core.factories import ApiClientFactory
from sccfm_core.types import ConfigLike
from sccfm_core.utils import validate_uids


class AsaUpgradeService:
    """Triggers ASA firmware/ASDM upgrades for single or multiple devices."""

    def __init__(self, config: ConfigLike) -> None:
        self._upgrades_api = DeviceUpgradesApi(ApiClientFactory().build(config=config))

    def upgrade_single(
        self,
        *,
        device_uid: str,
        software_version: str | None = None,
        asdm_version: str | None = None,
        stage_upgrade: bool = False,
        force_upgrade: bool = False,
        ignore_maintenance_window: bool = False,
        name: str | None = None,
    ) -> CdoTransaction:
        """Trigger an upgrade on a single ASA device.

        Returns the :class:`CdoTransaction` tracking the async operation.
        """
        validate_uids([device_uid])
        upgrade_input = UpgradeAsaDeviceInput(
            softwareVersion=software_version,
            asdmVersion=asdm_version,
            stageUpgrade=stage_upgrade,
            forceUpgrade=force_upgrade,
            ignoreMaintenanceWindow=ignore_maintenance_window,
            name=name,
        )
        return self._upgrades_api.upgrade_asa_device(
            device_uid=device_uid,
            upgrade_asa_device_input=upgrade_input,
        )

    def upgrade_multiple(
        self,
        *,
        device_uids: list[str],
        software_version: str | None = None,
        asdm_version: str | None = None,
        stage_upgrade: bool = False,
        force_upgrade: bool = False,
        ignore_maintenance_window: bool = False,
        name: str | None = None,
    ) -> CdoTransaction:
        """Trigger an upgrade on multiple ASA devices (up to 50).

        Returns the :class:`CdoTransaction` tracking the async operation.
        """
        validate_uids(device_uids)
        upgrade_input = UpgradeAsaDevicesInput(
            deviceUids=device_uids,
            softwareVersion=software_version,
            asdmVersion=asdm_version,
            stageUpgrade=stage_upgrade,
            forceUpgrade=force_upgrade,
            ignoreMaintenanceWindow=ignore_maintenance_window,
            name=name,
        )
        return self._upgrades_api.upgrade_asa_devices(
            upgrade_asa_devices_input=upgrade_input,
        )

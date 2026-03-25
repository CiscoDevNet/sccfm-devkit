from __future__ import annotations

from scc_firewall_manager_sdk import (
    CdoTransaction,
    FtdDeploymentInput,
    FtdMultiDeviceDeploymentInput,
    InventoryApi,
)

from sccfm_core.factories import ApiClientFactory
from sccfm_core.types import ConfigLike
from sccfm_core.utils import validate_uids


class FtdDeployService:
    """Deploys configuration changes to cdFMC-managed FTD devices."""

    def __init__(self, config: ConfigLike) -> None:
        self._inventory_api = InventoryApi(ApiClientFactory().build(config=config))

    def deploy_single(
        self,
        *,
        device_uid: str,
        deployment_notes: str | None = None,
        description: str | None = None,
        ignore_warnings: bool = False,
    ) -> CdoTransaction:
        """Deploy changes to a single cdFMC-managed FTD device.

        Returns the :class:`CdoTransaction` tracking the async operation.
        """
        validate_uids([device_uid])
        deployment_input = FtdDeploymentInput(
            deploymentNotes=deployment_notes,
            description=description,
            ignoreWarnings=ignore_warnings,
        )
        return self._inventory_api.deploy_ftd_device_changes(
            device_uid=device_uid,
            ftd_deployment_input=deployment_input,
        )

    def deploy_multiple(
        self,
        *,
        device_uids: list[str],
        deployment_notes: str | None = None,
        description: str | None = None,
        ignore_warnings: bool = False,
    ) -> CdoTransaction:
        """Deploy changes to multiple cdFMC-managed FTD devices (up to 50).

        Returns the :class:`CdoTransaction` tracking the async operation.
        """
        validate_uids(device_uids)
        deployment_input = FtdMultiDeviceDeploymentInput(
            deviceUids=device_uids,
            deploymentNotes=deployment_notes,
            description=description,
            ignoreWarnings=ignore_warnings,
        )
        return self._inventory_api.deploy_changes_to_multiple_ftd_devices(
            ftd_multi_device_deployment_input=deployment_input,
        )

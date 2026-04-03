from sccfm_core.services.inventory.asa_boot_image_service import AsaBootImageService
from sccfm_core.services.inventory.asa_boot_registry_service import (
    AsaBootRegistryService,
)
from sccfm_core.services.inventory.asa_cli_service import AsaCommandLineService
from sccfm_core.services.inventory.asa_disk_file_service import AsaDiskFileService
from sccfm_core.services.inventory.asa_onboard_service import AsaOnboardService
from sccfm_core.services.inventory.asa_shun_service import AsaShunService, ShunEntrySpec
from sccfm_core.services.inventory.asa_upgrade_service import AsaUpgradeService
from sccfm_core.services.inventory.asa_upgrade_version_service import (
    AsaUpgradeVersionService,
    AsdmCompatibilityInfo,
    get_asdm_compatibility_info,
    is_version_downgrade,
)
from sccfm_core.services.inventory.asa_user_password_service import (
    AsaUserPasswordService,
)
from sccfm_core.services.inventory.ftd_deploy_service import FtdDeployService
from sccfm_core.services.inventory.ftd_onboard_service import FtdOnboardService
from sccfm_core.services.inventory.ftd_upgrade_service import FtdUpgradeService
from sccfm_core.services.inventory.ftd_upgrade_version_service import (
    FtdUpgradeVersionService,
    resolve_upgrade_package_uid,
)
from sccfm_core.services.inventory.inventory_service import InventoryService

__all__ = [
    "AsdmCompatibilityInfo",
    "AsaBootImageService",
    "AsaBootRegistryService",
    "FtdDeployService",
    "FtdOnboardService",
    "AsaCommandLineService",
    "AsaDiskFileService",
    "AsaOnboardService",
    "AsaShunService",
    "AsaUpgradeService",
    "AsaUpgradeVersionService",
    "AsaUserPasswordService",
    "FtdUpgradeService",
    "FtdUpgradeVersionService",
    "InventoryService",
    "ShunEntrySpec",
    "get_asdm_compatibility_info",
    "is_version_downgrade",
    "resolve_upgrade_package_uid",
]

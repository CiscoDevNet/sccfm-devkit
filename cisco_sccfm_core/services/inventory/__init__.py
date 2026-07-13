# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from cisco_sccfm_core.services.inventory.asa_boot_image_service import AsaBootImageService
from cisco_sccfm_core.services.inventory.asa_boot_registry_service import AsaBootRegistryService
from cisco_sccfm_core.services.inventory.asa_cli_service import AsaCommandLineService
from cisco_sccfm_core.services.inventory.asa_disk_file_service import AsaDiskFileService
from cisco_sccfm_core.services.inventory.asa_ha_check_service import (
    AsaHaCheckReport,
    AsaHaCheckService,
)
from cisco_sccfm_core.services.inventory.asa_onboard_service import AsaOnboardService
from cisco_sccfm_core.services.inventory.asa_shun_service import AsaShunService, ShunEntrySpec
from cisco_sccfm_core.services.inventory.asa_upgrade_service import AsaUpgradeService
from cisco_sccfm_core.services.inventory.asa_upgrade_version_service import (
    AsaUpgradeVersionService,
    AsdmCompatibilityInfo,
    get_asdm_compatibility_info,
    is_version_downgrade,
)
from cisco_sccfm_core.services.inventory.asa_user_password_service import AsaUserPasswordService
from cisco_sccfm_core.services.inventory.cdfmc_access_policy_service import (
    CdfmcAccessPolicyService,
    FmcAccessPolicy,
    FmcAccessPolicyPage,
)
from cisco_sccfm_core.services.inventory.ftd_cli_service import FtdCommandLineService
from cisco_sccfm_core.services.inventory.ftd_configure_manager_service import (
    ConfigureManagerResult,
    FtdConfigureManagerError,
    FtdConfigureManagerService,
    JumpHostSpec,
    ReachabilityResult,
    parse_jump_host,
)
from cisco_sccfm_core.services.inventory.ftd_deploy_service import FtdDeployService
from cisco_sccfm_core.services.inventory.ftd_onboard_service import FtdOnboardService
from cisco_sccfm_core.services.inventory.ftd_upgrade_service import FtdUpgradeService
from cisco_sccfm_core.services.inventory.ftd_upgrade_version_service import (
    FtdUpgradeVersionService,
    resolve_upgrade_package_uid,
)
from cisco_sccfm_core.services.inventory.ftd_ztp_onboard_service import FtdZtpOnboardService
from cisco_sccfm_core.services.inventory.inventory_service import InventoryService

__all__ = [
    "AsdmCompatibilityInfo",
    "AsaBootImageService",
    "AsaBootRegistryService",
    "AsaCommandLineService",
    "AsaDiskFileService",
    "AsaHaCheckReport",
    "AsaHaCheckService",
    "AsaOnboardService",
    "AsaShunService",
    "AsaUpgradeService",
    "AsaUpgradeVersionService",
    "AsaUserPasswordService",
    "CdfmcAccessPolicyService",
    "ConfigureManagerResult",
    "FmcAccessPolicy",
    "FmcAccessPolicyPage",
    "FtdCommandLineService",
    "FtdConfigureManagerError",
    "FtdConfigureManagerService",
    "JumpHostSpec",
    "ReachabilityResult",
    "parse_jump_host",
    "FtdDeployService",
    "FtdOnboardService",
    "FtdZtpOnboardService",
    "FtdUpgradeService",
    "FtdUpgradeVersionService",
    "InventoryService",
    "ShunEntrySpec",
    "get_asdm_compatibility_info",
    "is_version_downgrade",
    "resolve_upgrade_package_uid",
]

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for cisco_sccfm_core.services.inventory.ftd_upgrade_service module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from scc_firewall_manager_sdk import (
    CdoTransaction,
    UpgradeFtdDeviceInput,
    UpgradeFtdDevicesInput,
)

from cisco_sccfm_core.services.inventory.ftd_upgrade_service import FtdUpgradeService


@pytest.fixture
def mock_config() -> MagicMock:
    config = MagicMock()
    config.region = "us"
    config.api_token = "test-token"
    return config


@pytest.fixture
def upgrade_service(mock_config: MagicMock) -> FtdUpgradeService:
    with patch("cisco_sccfm_core.services.inventory.ftd_upgrade_service.ApiClientFactory"):
        return FtdUpgradeService(config=mock_config)


def _fake_transaction(uid: str = "txn-1") -> CdoTransaction:
    return CdoTransaction(
        transactionUid=uid,
        cdoTransactionStatus="PENDING",
    )


class TestUpgradeSingle:
    def test_should_call_upgrade_ftd_device_with_correct_params(
        self, upgrade_service: FtdUpgradeService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_upgrade = MagicMock(return_value=_fake_transaction("txn-single"))
        monkeypatch.setattr(upgrade_service._upgrades_api, "upgrade_ftd_device", mock_upgrade)

        result = upgrade_service.upgrade_single(
            device_uid="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            upgrade_package_uid="pkg-uid-1234",
            stage_upgrade=True,
            ignore_maintenance_window=True,
            name="test-upgrade",
        )

        assert result.transaction_uid == "txn-single"
        call_kwargs = mock_upgrade.call_args
        assert call_kwargs.kwargs["device_uid"] == "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        input_obj: UpgradeFtdDeviceInput = call_kwargs.kwargs["upgrade_ftd_device_input"]
        assert input_obj.upgrade_package_uid == "pkg-uid-1234"
        assert input_obj.stage_upgrade is True
        assert input_obj.ignore_maintenance_window is True
        assert input_obj.name == "test-upgrade"

    def test_should_reject_invalid_uid(self, upgrade_service: FtdUpgradeService) -> None:
        with pytest.raises(ValueError, match="Invalid UUIDv4"):
            upgrade_service.upgrade_single(
                device_uid="not-a-uuid",
                upgrade_package_uid="pkg-uid-1234",
            )

    def test_should_pass_defaults(
        self, upgrade_service: FtdUpgradeService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_upgrade = MagicMock(return_value=_fake_transaction())
        monkeypatch.setattr(upgrade_service._upgrades_api, "upgrade_ftd_device", mock_upgrade)

        upgrade_service.upgrade_single(
            device_uid="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            upgrade_package_uid="pkg-uid-1234",
        )

        call_kwargs = mock_upgrade.call_args
        input_obj: UpgradeFtdDeviceInput = call_kwargs.kwargs["upgrade_ftd_device_input"]
        assert input_obj.stage_upgrade is False
        assert input_obj.ignore_maintenance_window is False
        assert input_obj.name is None


class TestUpgradeMultiple:
    def test_should_call_upgrade_ftd_devices_with_correct_params(
        self, upgrade_service: FtdUpgradeService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_upgrade = MagicMock(return_value=_fake_transaction("txn-multi"))
        monkeypatch.setattr(upgrade_service._upgrades_api, "upgrade_ftd_devices", mock_upgrade)
        uids = [
            "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
        ]

        result = upgrade_service.upgrade_multiple(
            device_uids=uids,
            upgrade_package_uid="pkg-uid-5678",
            stage_upgrade=False,
            ignore_maintenance_window=False,
            name="multi-upgrade",
        )

        assert result.transaction_uid == "txn-multi"
        call_kwargs = mock_upgrade.call_args
        input_obj: UpgradeFtdDevicesInput = call_kwargs.kwargs["upgrade_ftd_devices_input"]
        assert input_obj.device_uids == uids
        assert input_obj.upgrade_package_uid == "pkg-uid-5678"
        assert input_obj.stage_upgrade is False
        assert input_obj.ignore_maintenance_window is False
        assert input_obj.name == "multi-upgrade"

    def test_should_reject_invalid_uids(self, upgrade_service: FtdUpgradeService) -> None:
        with pytest.raises(ValueError, match="Invalid UUIDv4"):
            upgrade_service.upgrade_multiple(
                device_uids=["valid-nope", "also-bad"],
                upgrade_package_uid="pkg-uid-1234",
            )

    def test_should_pass_defaults(
        self, upgrade_service: FtdUpgradeService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_upgrade = MagicMock(return_value=_fake_transaction())
        monkeypatch.setattr(upgrade_service._upgrades_api, "upgrade_ftd_devices", mock_upgrade)
        uids = ["a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"]

        upgrade_service.upgrade_multiple(
            device_uids=uids,
            upgrade_package_uid="pkg-uid-1234",
        )

        call_kwargs = mock_upgrade.call_args
        input_obj: UpgradeFtdDevicesInput = call_kwargs.kwargs["upgrade_ftd_devices_input"]
        assert input_obj.stage_upgrade is False
        assert input_obj.ignore_maintenance_window is False
        assert input_obj.name is None

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for cisco_sccfm_core.services.inventory.asa_secure_client_service module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from scc_firewall_manager_sdk import (
    CdoTransaction,
    CompatibleSecureClientVersionDto,
    SecureClientPackageDto,
    SecureClientPlatformDto,
    TriggerSecureClientUpgradeInput,
)

from cisco_sccfm_core.services.inventory.asa_secure_client_service import (
    AsaSecureClientService,
    pick_latest_version,
)

DEVICE_UID = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
OTHER_DEVICE_UID = "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"


@pytest.fixture
def mock_config() -> MagicMock:
    config = MagicMock()
    config.region = "us"
    config.api_token = "test-token"
    return config


@pytest.fixture
def secure_client_service(mock_config: MagicMock) -> AsaSecureClientService:
    with patch(
        "cisco_sccfm_core.services.inventory.asa_secure_client_service.ApiClientFactory"
    ):
        return AsaSecureClientService(config=mock_config)


def _fake_transaction(uid: str = "txn-1") -> CdoTransaction:
    return CdoTransaction(transactionUid=uid, cdoTransactionStatus="PENDING")


class TestGetCompatibleVersions:
    def test_should_call_api_with_device_uids(
        self, secure_client_service: AsaSecureClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        versions = [
            CompatibleSecureClientVersionDto(version="5.1.15.287", platforms=[]),
            CompatibleSecureClientVersionDto(version="4.10.05095", platforms=[]),
        ]
        mock_page = MagicMock(items=versions)
        mock_get = MagicMock(return_value=mock_page)
        monkeypatch.setattr(
            secure_client_service._secure_client_api,
            "get_asa_compatible_secure_client_versions",
            mock_get,
        )

        result = secure_client_service.get_compatible_versions(device_uids=[DEVICE_UID])

        assert result == versions
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["device_uids"] == [DEVICE_UID]
        assert call_kwargs["limit"] == 50
        assert call_kwargs["offset"] == 0

    def test_should_return_empty_list_when_no_items(
        self, secure_client_service: AsaSecureClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_page = MagicMock(items=None)
        monkeypatch.setattr(
            secure_client_service._secure_client_api,
            "get_asa_compatible_secure_client_versions",
            MagicMock(return_value=mock_page),
        )

        result = secure_client_service.get_compatible_versions(device_uids=[DEVICE_UID])

        assert result == []

    def test_should_reject_invalid_uid(
        self, secure_client_service: AsaSecureClientService
    ) -> None:
        with pytest.raises(ValueError, match="Invalid UUIDv4"):
            secure_client_service.get_compatible_versions(device_uids=["not-a-uuid"])


class TestListInstalledPackages:
    def test_should_call_api_with_device_uid(
        self, secure_client_service: AsaSecureClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        packages = [
            SecureClientPackageDto(
                deviceUid=DEVICE_UID,
                fileName="cisco-secure-client-linux64-5.1.15.287-webdeploy-k9.pkg",
                uid="pkg-uid-1",
                version="5.1.15.287",
            )
        ]
        mock_page = MagicMock(items=packages)
        mock_get = MagicMock(return_value=mock_page)
        monkeypatch.setattr(
            secure_client_service._secure_client_api,
            "get_asa_secure_client_packages",
            mock_get,
        )

        result = secure_client_service.list_installed_packages(device_uid=DEVICE_UID)

        assert result == packages
        assert mock_get.call_args.kwargs["device_uid"] == DEVICE_UID


class TestPushPackage:
    def test_should_call_trigger_with_correct_input(
        self, secure_client_service: AsaSecureClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_trigger = MagicMock(return_value=_fake_transaction("txn-push"))
        monkeypatch.setattr(
            secure_client_service._secure_client_api,
            "trigger_secure_client_upgrade",
            mock_trigger,
        )
        platforms = [SecureClientPlatformDto(os="LINUX", cpuArchitecture="X86_64")]

        result = secure_client_service.push_package(
            device_uids=[DEVICE_UID, OTHER_DEVICE_UID],
            version="5.1.15.287",
            platforms=platforms,
            name="test-push",
        )

        assert result.transaction_uid == "txn-push"
        input_obj: TriggerSecureClientUpgradeInput = mock_trigger.call_args.kwargs[
            "trigger_secure_client_upgrade_input"
        ]
        assert input_obj.device_uids == [DEVICE_UID, OTHER_DEVICE_UID]
        assert input_obj.version == "5.1.15.287"
        assert input_obj.platforms == platforms
        assert input_obj.name == "test-push"

    def test_should_pass_defaults(
        self, secure_client_service: AsaSecureClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_trigger = MagicMock(return_value=_fake_transaction())
        monkeypatch.setattr(
            secure_client_service._secure_client_api,
            "trigger_secure_client_upgrade",
            mock_trigger,
        )

        secure_client_service.push_package(device_uids=[DEVICE_UID], version="5.1.15.287")

        input_obj: TriggerSecureClientUpgradeInput = mock_trigger.call_args.kwargs[
            "trigger_secure_client_upgrade_input"
        ]
        assert input_obj.platforms is None
        assert input_obj.name is None

    def test_should_reject_invalid_uids(
        self, secure_client_service: AsaSecureClientService
    ) -> None:
        with pytest.raises(ValueError, match="Invalid UUIDv4"):
            secure_client_service.push_package(device_uids=["nope"], version="5.1.15.287")


class TestPickLatestVersion:
    def test_should_return_none_for_empty_list(self) -> None:
        assert pick_latest_version([]) is None

    def test_should_pick_highest_dotted_version(self) -> None:
        versions = [
            CompatibleSecureClientVersionDto(version="4.10.05095", platforms=[]),
            CompatibleSecureClientVersionDto(version="5.1.15.287", platforms=[]),
            CompatibleSecureClientVersionDto(version="4.10.04071", platforms=[]),
        ]

        result = pick_latest_version(versions)

        assert result is not None
        assert result.version == "5.1.15.287"

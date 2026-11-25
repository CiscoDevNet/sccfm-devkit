# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for cisco_sccfm_core.services.inventory.asa_secure_client_service module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from scc_firewall_manager_sdk import (
    ApiException,
    CdoTransaction,
    CompatibleSecureClientVersionDto,
    SecureClientPackageDto,
    SecureClientPlatformDto,
    TriggerSecureClientUpgradeInput,
)

from cisco_sccfm_core.services.inventory.asa_secure_client_service import (
    AsaSecureClientService,
    _call_retrying_transient_server_errors,
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


class TestWaitForSoftwareVersion:
    """Regression tests for the 2026-11-25 fix: CDO UI confirmed a device can
    show Synced/Online while its software version is still blank, which is
    what actually causes get_compatible_versions to 500 right after a sync."""

    def test_should_return_immediately_when_already_populated(
        self, secure_client_service: AsaSecureClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_inventory = MagicMock()
        mock_inventory.get_device_by_uid.return_value = MagicMock(software_version="9.18(4)")
        monkeypatch.setattr(
            "cisco_sccfm_core.services.inventory.asa_secure_client_service.InventoryService",
            MagicMock(return_value=mock_inventory),
        )
        mock_sleep = MagicMock()
        monkeypatch.setattr(
            "cisco_sccfm_core.services.inventory.asa_secure_client_service.time.sleep",
            mock_sleep,
        )

        secure_client_service.wait_for_software_version(device_uids=[DEVICE_UID])

        mock_sleep.assert_not_called()
        mock_inventory.get_device_by_uid.assert_called_once_with(device_uid=DEVICE_UID)

    def test_should_poll_until_version_appears(
        self, secure_client_service: AsaSecureClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_inventory = MagicMock()
        mock_inventory.get_device_by_uid.side_effect = [
            MagicMock(software_version=None),
            MagicMock(software_version=""),
            MagicMock(software_version="9.18(4)"),
        ]
        monkeypatch.setattr(
            "cisco_sccfm_core.services.inventory.asa_secure_client_service.InventoryService",
            MagicMock(return_value=mock_inventory),
        )
        mock_sleep = MagicMock()
        monkeypatch.setattr(
            "cisco_sccfm_core.services.inventory.asa_secure_client_service.time.sleep",
            mock_sleep,
        )

        secure_client_service.wait_for_software_version(device_uids=[DEVICE_UID])

        assert mock_inventory.get_device_by_uid.call_count == 3
        assert mock_sleep.call_count == 2

    def test_should_raise_timeout_error_when_never_populated(
        self, secure_client_service: AsaSecureClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_inventory = MagicMock()
        mock_inventory.get_device_by_uid.return_value = MagicMock(software_version=None)
        monkeypatch.setattr(
            "cisco_sccfm_core.services.inventory.asa_secure_client_service.InventoryService",
            MagicMock(return_value=mock_inventory),
        )
        monkeypatch.setattr(
            "cisco_sccfm_core.services.inventory.asa_secure_client_service.time.sleep",
            MagicMock(),
        )

        # Negative timeout forces the deadline check to fail on the very
        # first pass, so this doesn't need many iterations to time out.
        with pytest.raises(TimeoutError, match=DEVICE_UID):
            secure_client_service.wait_for_software_version(
                device_uids=[DEVICE_UID], timeout_sec=-1, poll_interval_sec=0
            )

    def test_should_track_multiple_devices_independently(
        self, secure_client_service: AsaSecureClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A device that already has a version shouldn't be re-polled once it
        clears, even while another device in the same batch is still pending."""
        responses = {
            DEVICE_UID: [MagicMock(software_version="9.18(4)")],
            OTHER_DEVICE_UID: [
                MagicMock(software_version=None),
                MagicMock(software_version="9.18(4)"),
            ],
        }
        call_counts = {DEVICE_UID: 0, OTHER_DEVICE_UID: 0}

        def fake_get_device(device_uid: str) -> MagicMock:
            index = call_counts[device_uid]
            call_counts[device_uid] += 1
            return responses[device_uid][index]

        mock_inventory = MagicMock()
        mock_inventory.get_device_by_uid.side_effect = fake_get_device
        monkeypatch.setattr(
            "cisco_sccfm_core.services.inventory.asa_secure_client_service.InventoryService",
            MagicMock(return_value=mock_inventory),
        )
        monkeypatch.setattr(
            "cisco_sccfm_core.services.inventory.asa_secure_client_service.time.sleep",
            MagicMock(),
        )

        secure_client_service.wait_for_software_version(
            device_uids=[DEVICE_UID, OTHER_DEVICE_UID]
        )

        assert call_counts[DEVICE_UID] == 1
        assert call_counts[OTHER_DEVICE_UID] == 2


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
        # limit/offset are string-typed on this beta endpoint's SDK model,
        # unlike InventoryService.get_devices' int params - see service docstring.
        assert call_kwargs["limit"] == "50"
        assert call_kwargs["offset"] == "0"

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

    def test_should_retry_transient_server_error_and_succeed(
        self, secure_client_service: AsaSecureClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression test for the 2026-11-24 live-run failure: a bare 500
        from this beta endpoint should be retried, not fail the whole task."""
        monkeypatch.setattr(
            "cisco_sccfm_core.services.inventory.asa_secure_client_service.time.sleep",
            MagicMock(),
        )
        versions = [CompatibleSecureClientVersionDto(version="5.1.15.287", platforms=[])]
        mock_page = MagicMock(items=versions)
        mock_get = MagicMock(
            side_effect=[
                ApiException(status=500, reason="Internal Server Error"),
                mock_page,
            ]
        )
        monkeypatch.setattr(
            secure_client_service._secure_client_api,
            "get_asa_compatible_secure_client_versions",
            mock_get,
        )

        result = secure_client_service.get_compatible_versions(device_uids=[DEVICE_UID])

        assert result == versions
        assert mock_get.call_count == 2

    def test_should_give_up_after_exhausting_retries(
        self, secure_client_service: AsaSecureClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "cisco_sccfm_core.services.inventory.asa_secure_client_service.time.sleep",
            MagicMock(),
        )
        mock_get = MagicMock(
            side_effect=ApiException(status=500, reason="Internal Server Error")
        )
        monkeypatch.setattr(
            secure_client_service._secure_client_api,
            "get_asa_compatible_secure_client_versions",
            mock_get,
        )

        with pytest.raises(ApiException):
            secure_client_service.get_compatible_versions(device_uids=[DEVICE_UID])

        assert mock_get.call_count == 3

    def test_should_not_retry_non_server_error(
        self, secure_client_service: AsaSecureClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_get = MagicMock(side_effect=ApiException(status=404, reason="Not Found"))
        monkeypatch.setattr(
            secure_client_service._secure_client_api,
            "get_asa_compatible_secure_client_versions",
            mock_get,
        )

        with pytest.raises(ApiException):
            secure_client_service.get_compatible_versions(device_uids=[DEVICE_UID])

        assert mock_get.call_count == 1


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

    def test_should_retry_transient_server_error_and_succeed(
        self, secure_client_service: AsaSecureClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "cisco_sccfm_core.services.inventory.asa_secure_client_service.time.sleep",
            MagicMock(),
        )
        packages = [
            SecureClientPackageDto(
                deviceUid=DEVICE_UID,
                fileName="cisco-secure-client-linux64-5.1.15.287-webdeploy-k9.pkg",
                uid="pkg-uid-1",
                version="5.1.15.287",
            )
        ]
        mock_page = MagicMock(items=packages)
        mock_get = MagicMock(
            side_effect=[
                ApiException(status=503, reason="Service Unavailable"),
                mock_page,
            ]
        )
        monkeypatch.setattr(
            secure_client_service._secure_client_api,
            "get_asa_secure_client_packages",
            mock_get,
        )

        result = secure_client_service.list_installed_packages(device_uid=DEVICE_UID)

        assert result == packages
        assert mock_get.call_count == 2


class TestCallRetryingTransientServerErrors:
    """Unit tests for the retry helper itself, independent of any one caller."""

    def test_should_return_result_on_first_success(self) -> None:
        call = MagicMock(return_value="ok")

        assert _call_retrying_transient_server_errors(call) == "ok"
        assert call.call_count == 1

    def test_should_sleep_with_increasing_backoff_between_retries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_sleep = MagicMock()
        monkeypatch.setattr(
            "cisco_sccfm_core.services.inventory.asa_secure_client_service.time.sleep",
            mock_sleep,
        )
        call = MagicMock(
            side_effect=[
                ApiException(status=500, reason="Internal Server Error"),
                ApiException(status=502, reason="Bad Gateway"),
                "ok",
            ]
        )

        assert _call_retrying_transient_server_errors(call) == "ok"
        assert mock_sleep.call_args_list == [((5.0,),), ((10.0,),)]


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

"""Tests for sccfm_core.errors module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from sccfm_core.errors import SccApiError


def _create_mock_api_exception(
    status: int | None = None,
    body: str | None = None,
) -> MagicMock:
    """Create a mock ApiException for testing."""
    exc = MagicMock()
    exc.status = status
    exc.body = body
    exc.__str__ = MagicMock(return_value=f"({status})\nReason: Test error")  # type: ignore[method-assign]
    return exc


class TestFromException:
    """Tests for SccApiError.from_exception()."""

    def test_should_parse_valid_json_body_with_all_fields(self) -> None:
        """from_exception should parse JSON body with all fields."""
        body = '{"errorMsg": "Device not found", "errorCode": "NOT_FOUND", "details": {"deviceId": "123"}}'
        exc = _create_mock_api_exception(status=404, body=body)

        error = SccApiError.from_exception(exc)

        assert error.message == "Device not found"
        assert error.error_code == "NOT_FOUND"
        assert error.details == {"deviceId": "123"}
        assert error.status_code == 404
        assert error.api_error == {
            "errorMsg": "Device not found",
            "errorCode": "NOT_FOUND",
            "details": {"deviceId": "123"},
        }

    def test_should_preserve_cisco_messages_schema(self) -> None:
        """from_exception should preserve Cisco's category/messages/severity body."""
        body = """
        {
          "category": "VALIDATION",
          "messages": [
            {
              "code": "INVALID_COMMAND",
              "description": "Only show commands are supported",
              "severity": "ERROR"
            }
          ],
          "severity": "ERROR"
        }
        """
        exc = _create_mock_api_exception(status=400, body=body)

        error = SccApiError.from_exception(exc)

        assert error.message == "Only show commands are supported"
        assert error.error_code == "INVALID_COMMAND"
        assert error.details is None
        assert error.status_code == 400
        assert error.api_error == {
            "category": "VALIDATION",
            "messages": [
                {
                    "code": "INVALID_COMMAND",
                    "description": "Only show commands are supported",
                    "severity": "ERROR",
                }
            ],
            "severity": "ERROR",
        }

    def test_should_parse_json_body_with_missing_optional_fields(self) -> None:
        """from_exception should handle JSON body with only errorMsg."""
        body = '{"errorMsg": "Something went wrong"}'
        exc = _create_mock_api_exception(status=500, body=body)

        error = SccApiError.from_exception(exc)

        assert error.message == "Something went wrong"
        assert error.error_code is None
        assert error.details is None
        assert error.status_code == 500

    def test_should_fallback_for_non_json_body(self) -> None:
        """from_exception should use str(exc) for non-JSON body."""
        exc = _create_mock_api_exception(status=500, body="Internal Server Error")

        error = SccApiError.from_exception(exc)

        assert "500" in error.message
        assert error.error_code is None
        assert error.details is None
        assert error.status_code == 500

    def test_should_handle_empty_body(self) -> None:
        """from_exception should handle empty body string."""
        exc = _create_mock_api_exception(status=503, body="")

        error = SccApiError.from_exception(exc)

        assert "503" in error.message
        assert error.status_code == 503

    def test_should_handle_none_body(self) -> None:
        """from_exception should handle None body."""
        exc = _create_mock_api_exception(status=401, body=None)

        error = SccApiError.from_exception(exc)

        assert "401" in error.message
        assert error.status_code == 401

    def test_should_fallback_when_errormsg_missing_in_json(self) -> None:
        """from_exception should fallback to str(exc) when errorMsg missing."""
        body = '{"errorCode": "INVALID", "details": {}}'
        exc = _create_mock_api_exception(status=400, body=body)

        error = SccApiError.from_exception(exc)

        assert "400" in error.message  # Falls back to str(exc)
        assert error.error_code == "INVALID"
        assert error.details == {}
        assert error.status_code == 400


class TestToDict:
    """Tests for SccApiError.to_dict()."""

    def test_should_return_dict_with_correct_keys(self) -> None:
        """to_dict should return dict with Ansible-compatible keys."""
        error = SccApiError(
            message="Test error",
            error_code="TEST_CODE",
            details={"key": "value"},
            status_code=400,
        )

        result = error.to_dict()

        assert result == {
            "msg": "Test error",
            "error_code": "TEST_CODE",
            "error_details": {"key": "value"},
            "status_code": 400,
        }

    def test_should_include_none_values(self) -> None:
        """to_dict should include None for missing optional fields."""
        error = SccApiError(message="Error only")

        result = error.to_dict()

        assert result == {
            "msg": "Error only",
            "error_code": None,
            "error_details": None,
            "status_code": None,
        }

    def test_should_include_raw_api_error_when_available(self) -> None:
        """to_dict should retain the original API error body for JSON callers."""
        error = SccApiError(
            message="Only show commands are supported",
            error_code="INVALID_COMMAND",
            status_code=400,
            api_error={
                "category": "VALIDATION",
                "messages": [{"code": "INVALID_COMMAND"}],
                "severity": "ERROR",
            },
        )

        result = error.to_dict()

        assert result["api_error"] == {
            "category": "VALIDATION",
            "messages": [{"code": "INVALID_COMMAND"}],
            "severity": "ERROR",
        }


class TestStr:
    """Tests for SccApiError.__str__()."""

    def test_should_format_message_only(self) -> None:
        """__str__ should format with message only."""
        error = SccApiError(message="Simple error")

        result = str(error)

        assert result == "Simple error"

    def test_should_format_with_error_code(self) -> None:
        """__str__ should include error code when present."""
        error = SccApiError(message="Error occurred", error_code="ERR_001")

        result = str(error)

        assert "Error occurred" in result
        assert "Error Code: ERR_001" in result

    def test_should_format_with_details(self) -> None:
        """__str__ should include details when present."""
        error = SccApiError(
            message="Error with details",
            error_code="ERR_002",
            details={"field": "value"},
        )

        result = str(error)

        assert "Error with details" in result
        assert "Error Code: ERR_002" in result
        assert '"field": "value"' in result

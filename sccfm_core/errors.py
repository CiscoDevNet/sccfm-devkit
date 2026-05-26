# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Error handling utilities for SCC Firewall Manager API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scc_firewall_manager_sdk import ApiException


@dataclass
class SccApiError:
    """Parsed error info from SCC Firewall Manager API.

    This class provides a structured representation of API errors,
    extracting the errorMsg, errorCode, and details fields from the
    JSON response body.
    """

    message: str
    error_code: str | None = None
    details: dict[str, Any] | None = None
    status_code: int | None = None
    api_error: dict[str, Any] | None = None

    @classmethod
    def from_exception(cls, exc: ApiException) -> SccApiError:
        """Parse an ApiException into structured error info.

        Handles:
        - JSON body with errorMsg/errorCode/details fields
        - Non-JSON body (falls back to string representation)
        - Missing fields (graceful degradation)

        Args:
            exc: The ApiException raised by the SDK.

        Returns:
            A SccApiError with parsed error information.
        """
        status_code = getattr(exc, "status", None)

        if exc.body:
            try:
                raw_body = json.loads(exc.body)
                if not isinstance(raw_body, dict):
                    return cls(message=str(exc), status_code=status_code)
                body: dict[str, Any] = raw_body
                return cls(
                    message=_extract_error_message(body=body, fallback=str(exc)),
                    error_code=_extract_error_code(body=body),
                    details=body.get("details"),
                    status_code=status_code,
                    api_error=body,
                )
            except json.JSONDecodeError:
                pass

        return cls(message=str(exc), status_code=status_code)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for Ansible fail_json().

        Returns:
            A dictionary with keys matching Ansible's fail_json() parameters.
        """
        payload: dict[str, Any] = {
            "msg": self.message,
            "error_code": self.error_code,
            "error_details": self.details,
            "status_code": self.status_code,
        }
        if self.api_error is not None:
            payload["api_error"] = self.api_error
        return payload

    def __str__(self) -> str:
        """Human-readable format for CLI output."""
        lines = [self.message]
        if self.error_code:
            lines.append(f"Error Code: {self.error_code}")
        if self.details:
            lines.append(f"Details: {json.dumps(self.details, indent=2)}")
        return "\n".join(lines)


class NotFoundError(Exception):
    """Exception raised when a resource is not found."""

    pass


def _extract_error_message(*, body: dict[str, Any], fallback: str) -> str:
    error_msg = body.get("errorMsg")
    if isinstance(error_msg, str) and error_msg:
        return error_msg

    first_message = _first_error_message(body)
    if first_message is not None:
        for key in ("description", "details", "message", "code", "errorCode"):
            value = first_message.get(key)
            if isinstance(value, str) and value:
                return value

    return fallback


def _extract_error_code(*, body: dict[str, Any]) -> str | None:
    error_code = body.get("errorCode")
    if isinstance(error_code, str) and error_code:
        return error_code

    first_message = _first_error_message(body)
    if first_message is None:
        return None

    for key in ("errorCode", "code"):
        value = first_message.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _first_error_message(body: dict[str, Any]) -> dict[str, Any] | None:
    messages = body.get("messages")
    if messages is None and isinstance(body.get("error"), dict):
        messages = body["error"].get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    first = messages[0]
    return first if isinstance(first, dict) else None

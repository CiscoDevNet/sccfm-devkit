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
                body = json.loads(exc.body)
                return cls(
                    message=body.get("errorMsg", str(exc)),
                    error_code=body.get("errorCode"),
                    details=body.get("details"),
                    status_code=status_code,
                )
            except json.JSONDecodeError:
                pass

        return cls(message=str(exc), status_code=status_code)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for Ansible fail_json().

        Returns:
            A dictionary with keys matching Ansible's fail_json() parameters.
        """
        return {
            "msg": self.message,
            "error_code": self.error_code,
            "error_details": self.details,
            "status_code": self.status_code,
        }

    def __str__(self) -> str:
        """Human-readable format for CLI output."""
        lines = [self.message]
        if self.error_code:
            lines.append(f"Error Code: {self.error_code}")
        if self.details:
            lines.append(f"Details: {json.dumps(self.details, indent=2)}")
        return "\n".join(lines)

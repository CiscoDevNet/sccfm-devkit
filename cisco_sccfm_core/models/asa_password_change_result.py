# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AsaPasswordChangeResult:
    """Result of a password change attempt on a single ASA device."""

    device_uid: str
    status: str  # "success" | "failed" | "user_not_found"
    message: str

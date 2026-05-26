# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AsaBootImageChangeResult:
    """Result of checking or changing the boot image on a single ASA device."""

    device_uid: str
    requested_image_path: str
    status: str
    message: str
    boot_system_entries_before: list[str] = field(default_factory=list)
    boot_system_entries_after: list[str] = field(default_factory=list)

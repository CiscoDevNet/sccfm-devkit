# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AsaBootRegistry:
    """Boot registry information extracted from ASA ``show version``,
    ``show run boot``, and config-register lines."""

    system_image_file: str
    compiled_date: str
    config_register: str
    config_modified: bool
    boot_system_entries: list[str] = field(default_factory=list)

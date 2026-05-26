# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re

from sccfm_core.models.asa_boot_registry import AsaBootRegistry

# ── show version patterns ────────────────────────────────────────

# "System image file is "disk0:/asa9191-41-lfbff-k8.SPA""
_SYSTEM_IMAGE_RE = re.compile(
    r'System image file is\s+"([^"]+)"',
    re.IGNORECASE,
)

# "Compiled on Wed 13-Mar-24 02:50 GMT by builders"
_COMPILED_RE = re.compile(
    r"Compiled on\s+(.+?)(?:\s+by\s+\S+)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# "Configuration register is 0x1"
_CONFIG_REGISTER_RE = re.compile(
    r"Configuration register is\s+(0x[\da-fA-F]+)",
    re.IGNORECASE,
)

# "Configuration has not been modified since last system restart."
# vs. absence of this line (implying it *has* been modified)
_CONFIG_NOT_MODIFIED_RE = re.compile(
    r"Configuration has not been modified since last system restart",
    re.IGNORECASE,
)

# ── show run boot pattern ────────────────────────────────────────

# "boot system disk0:/asa9191-41-lfbff-k8.SPA"
_BOOT_SYSTEM_RE = re.compile(
    r"^\s*boot\s+system\s+(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_boot_registry(
    show_version_output: str,
    show_run_boot_output: str,
) -> AsaBootRegistry:
    """Parse ``show version`` and ``show run boot`` output into a
    :class:`AsaBootRegistry` model.

    Both inputs are raw text returned by the ASA CLI.
    """
    system_image_file = _extract(_SYSTEM_IMAGE_RE, show_version_output, default="unknown")
    compiled_date = _extract(_COMPILED_RE, show_version_output, default="unknown")
    config_register = _extract(_CONFIG_REGISTER_RE, show_version_output, default="unknown")
    config_modified = not bool(_CONFIG_NOT_MODIFIED_RE.search(show_version_output))

    boot_entries = _BOOT_SYSTEM_RE.findall(show_run_boot_output)

    return AsaBootRegistry(
        system_image_file=system_image_file,
        compiled_date=compiled_date,
        config_register=config_register,
        config_modified=config_modified,
        boot_system_entries=[entry.strip() for entry in boot_entries],
    )


def _extract(pattern: re.Pattern[str], text: str, *, default: str) -> str:
    """Return the first capture group from *pattern*, or *default*."""
    match = pattern.search(text)
    return match.group(1).strip() if match else default

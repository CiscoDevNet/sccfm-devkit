# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AsaDiskFileType(str, Enum):
    """Classification of files found on an ASA device disk."""

    OS_IMAGE = "OS_IMAGE"
    ANYCONNECT_PACKAGE = "ANYCONNECT_PACKAGE"
    ASDM_IMAGE = "ASDM_IMAGE"
    OTHER = "OTHER"


def classify_file(filename: str) -> AsaDiskFileType:
    """Classify a file based on its name."""
    lower = filename.lower()
    if (lower.startswith("asa") or lower.startswith("cisco-asa")) and lower.endswith(
        (".bin", ".spa")
    ):
        return AsaDiskFileType.OS_IMAGE
    if lower.startswith("asdm") and lower.endswith(".bin"):
        return AsaDiskFileType.ASDM_IMAGE
    if lower.startswith("anyconnect") and lower.endswith(".pkg"):
        return AsaDiskFileType.ANYCONNECT_PACKAGE
    return AsaDiskFileType.OTHER


@dataclass(frozen=True)
class AsaDiskFile:
    """A single file entry from an ASA device disk listing."""

    name: str
    size: int
    date: str
    file_type: AsaDiskFileType

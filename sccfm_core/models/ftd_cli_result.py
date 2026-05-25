# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FtdDeviceCliResponse:
    """CLI output for a single FTD device from the cdFMC bulk command endpoint."""

    device_uuid: str
    device_name: str
    response: str | None
    is_error: bool
    error_msg: str | None = None


@dataclass(frozen=True)
class FtdBulkCliResult:
    """Parsed download report from a cdFMC bulk CLI command execution."""

    command: str
    device_responses: list[FtdDeviceCliResponse]

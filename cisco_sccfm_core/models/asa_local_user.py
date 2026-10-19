# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AsaLocalUser:
    """Parsed representation of a local user from ASA running config.

    Represents a line like:
        username admin password DLaUiAX3l78qgoB5c7iVNw== encrypted privilege 15
    """

    username: str
    encrypted_password: str
    privilege_level: int

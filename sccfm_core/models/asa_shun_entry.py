# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AsaShunEntry:
    """Parsed representation of a shun entry from ``show shun`` output.

    Represents a line like::

        shun (outside) 10.1.1.27 10.2.2.89 555 666 6
    """

    interface: str
    source_ip: str
    destination_ip: str
    source_port: int
    destination_port: int
    protocol: int


@dataclass(frozen=True)
class AsaShunInterfaceStats:
    """Per-interface shun statistics from ``show shun statistics``.

    Represents a line like::

        outside=gilligan 0 Shunned, 10 received
    """

    interface: str
    shunned: int
    received: int

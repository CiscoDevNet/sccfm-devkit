# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    profile: str
    region: str
    api_token: str = field(repr=False)

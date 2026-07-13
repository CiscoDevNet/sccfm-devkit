# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Protocol


class ConfigLike(Protocol):
    @property
    def region(self) -> str: ...

    @property
    def api_token(self) -> str: ...

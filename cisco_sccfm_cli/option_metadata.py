# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Metadata helpers for Click options exposed through the CLI schema."""

from __future__ import annotations

from typing import TypeVar

import click

_SENSITIVE_ATTRIBUTE = "_sccfm_sensitive"

_OptionT = TypeVar("_OptionT", bound=click.Option)


def sensitive_option(option: _OptionT) -> _OptionT:
    """Mark an option value as sensitive without changing its input behavior."""
    setattr(option, _SENSITIVE_ATTRIBUTE, True)
    return option


def is_sensitive_option(option: click.Option) -> bool:
    """Return whether an option contains a credential or other secret value."""
    return bool(getattr(option, _SENSITIVE_ATTRIBUTE, False) or option.hide_input)

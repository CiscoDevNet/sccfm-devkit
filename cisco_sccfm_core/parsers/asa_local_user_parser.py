# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re

from cisco_sccfm_core.models.asa_local_user import AsaLocalUser

# Matches a username line from ``show running-config username <user>`` output.
#
# Examples:
#   username admin password DLaUiAX3l78qgoB5c7iVNw== encrypted privilege 15
#   username admin password $sha512$... pbkdf2 privilege 15
#   username cisco password DbYlpZO9Ij9uvfuF encrypted
#   username admin password ***** pbkdf2 privilege 15
_USERNAME_LINE_RE = re.compile(
    r"^\s*username\s+"
    r"(\S+)\s+"  # username (group 1)
    r"password\s+"
    r"(\S+)\s+"  # encrypted password hash (group 2)
    r"(?:encrypted|pbkdf2)"  # hash type keyword (not captured)
    r"(?:\s+privilege\s+(\d+))?"  # optional privilege level (group 3)
)

_DEFAULT_PRIVILEGE_LEVEL = 0


def parse_local_user(raw_output: str) -> AsaLocalUser | None:
    """Parse the output of ``show running-config username <user>``.

    Looks for the first line matching the expected username/password format.
    Returns an :class:`AsaLocalUser` if found, or ``None`` if the user
    does not exist in the output.

    When the privilege level is omitted the ASA defaults to 0.
    """
    for line in raw_output.splitlines():
        match = _USERNAME_LINE_RE.match(line)
        if match:
            username, encrypted_password, privilege_str = match.groups()
            privilege_level = int(privilege_str) if privilege_str else _DEFAULT_PRIVILEGE_LEVEL
            return AsaLocalUser(
                username=username,
                encrypted_password=encrypted_password,
                privilege_level=privilege_level,
            )
    return None

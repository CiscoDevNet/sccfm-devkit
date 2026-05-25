# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for sccfm_core.parsers.asa_local_user_parser module."""

from __future__ import annotations

from sccfm_core.models.asa_local_user import AsaLocalUser
from sccfm_core.parsers.asa_local_user_parser import parse_local_user

SAMPLE_OUTPUT_ENCRYPTED = """\
username admin password DLaUiAX3l78qgoB5c7iVNw== encrypted privilege 15
"""

SAMPLE_OUTPUT_PBKDF2 = """\
username admin password $sha512$rounds=10000$abc123def456$longhashvalue== pbkdf2 privilege 15
"""

SAMPLE_OUTPUT_WITH_ATTRIBUTES = """\
username admin password DLaUiAX3l78qgoB5c7iVNw== encrypted privilege 15
username admin attributes
 service-type admin
"""

SAMPLE_OUTPUT_LOW_PRIVILEGE = """\
username readonly password Xk9mPz2Qr8sT4w== encrypted privilege 1
"""

SAMPLE_OUTPUT_NO_PRIVILEGE = """\
username cisco password DbYlpZO9Ij9uvfuF encrypted
"""

SAMPLE_OUTPUT_REDACTED_HASH = """\
username admin password ***** pbkdf2 privilege 15
"""


class TestParseLocalUser:
    """Tests for parse_local_user()."""

    def test_should_parse_encrypted_password(self) -> None:
        """Parser should extract user with 'encrypted' keyword."""
        user = parse_local_user(SAMPLE_OUTPUT_ENCRYPTED)
        assert user is not None
        assert user.username == "admin"
        assert user.encrypted_password == "DLaUiAX3l78qgoB5c7iVNw=="
        assert user.privilege_level == 15

    def test_should_parse_pbkdf2_password(self) -> None:
        """Parser should extract user with 'pbkdf2' keyword."""
        user = parse_local_user(SAMPLE_OUTPUT_PBKDF2)
        assert user is not None
        assert user.username == "admin"
        assert user.encrypted_password == "$sha512$rounds=10000$abc123def456$longhashvalue=="
        assert user.privilege_level == 15

    def test_should_parse_first_password_line_with_attributes(self) -> None:
        """Parser should return the password line, ignoring attribute lines."""
        user = parse_local_user(SAMPLE_OUTPUT_WITH_ATTRIBUTES)
        assert user is not None
        assert user.username == "admin"
        assert user.encrypted_password == "DLaUiAX3l78qgoB5c7iVNw=="

    def test_should_parse_low_privilege_user(self) -> None:
        """Parser should handle non-15 privilege levels."""
        user = parse_local_user(SAMPLE_OUTPUT_LOW_PRIVILEGE)
        assert user is not None
        assert user.username == "readonly"
        assert user.privilege_level == 1

    def test_should_return_none_for_empty_output(self) -> None:
        """Parser should return None when output is empty."""
        assert parse_local_user("") is None

    def test_should_return_none_when_user_not_found(self) -> None:
        """Parser should return None when no matching line is present."""
        output = "ERROR: username not found\n"
        assert parse_local_user(output) is None

    def test_should_skip_malformed_lines(self) -> None:
        """Parser should skip lines that don't match and find valid ones."""
        output = """\
some random garbage
username admin password DLaUiAX3l78qgoB5c7iVNw== encrypted privilege 15
more garbage
"""
        user = parse_local_user(output)
        assert user is not None
        assert user.username == "admin"

    def test_should_parse_user_without_privilege_level(self) -> None:
        """Parser should default privilege to 0 when not specified."""
        user = parse_local_user(SAMPLE_OUTPUT_NO_PRIVILEGE)
        assert user is not None
        assert user.username == "cisco"
        assert user.encrypted_password == "DbYlpZO9Ij9uvfuF"
        assert user.privilege_level == 0

    def test_should_parse_redacted_hash(self) -> None:
        """Parser should handle SCCFM-redacted password hashes."""
        user = parse_local_user(SAMPLE_OUTPUT_REDACTED_HASH)
        assert user is not None
        assert user.username == "admin"
        assert user.encrypted_password == "*****"
        assert user.privilege_level == 15

    def test_should_return_frozen_dataclass_instance(self) -> None:
        """Parsed user should be an immutable frozen dataclass instance."""
        user = parse_local_user(SAMPLE_OUTPUT_ENCRYPTED)
        assert isinstance(user, AsaLocalUser)
        try:
            user.username = "changed"  # type: ignore[misc,unused-ignore]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass

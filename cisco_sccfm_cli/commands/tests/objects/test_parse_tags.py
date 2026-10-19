# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import click
import pytest

from cisco_sccfm_cli.commands.objects.options import parse_tags


class TestParseTagsKeyValue:
    """Tests for key=value tag format."""

    def test_single_key_value(self) -> None:
        result = parse_tags(("env=prod",))
        assert result == {"env": ["prod"]}

    def test_comma_separated_values(self) -> None:
        result = parse_tags(("env=prod,staging",))
        assert result == {"env": ["prod", "staging"]}

    def test_multiple_tags(self) -> None:
        result = parse_tags(("env=prod", "team=security"))
        assert result == {"env": ["prod"], "team": ["security"]}

    def test_duplicate_keys_are_merged(self) -> None:
        result = parse_tags(("env=prod", "env=staging"))
        assert result == {"env": ["prod", "staging"]}

    def test_empty_key_raises_error(self) -> None:
        with pytest.raises(click.BadParameter, match="Tag key cannot be empty"):
            parse_tags(("=prod",))

    def test_empty_value_raises_error(self) -> None:
        with pytest.raises(click.BadParameter, match="must include at least one value"):
            parse_tags(("env=",))

    def test_whitespace_is_stripped(self) -> None:
        result = parse_tags((" env = prod , staging ",))
        assert result == {"env": ["prod", "staging"]}


class TestParseTagsStandalone:
    """Tests for standalone tag format (stored under 'labels' key)."""

    def test_single_standalone_tag(self) -> None:
        result = parse_tags(("production",))
        assert result == {"labels": ["production"]}

    def test_comma_separated_standalone_tags(self) -> None:
        result = parse_tags(("production,staging",))
        assert result == {"labels": ["production", "staging"]}

    def test_multiple_standalone_tags(self) -> None:
        result = parse_tags(("production", "staging"))
        assert result == {"labels": ["production", "staging"]}

    def test_ignores_empty_segments(self) -> None:
        result = parse_tags(("production,,staging,",))
        assert result == {"labels": ["production", "staging"]}


class TestParseTagsMixed:
    """Tests for mixed key=value and standalone tags."""

    def test_mixed_tags_and_labels(self) -> None:
        result = parse_tags(("env=prod", "production"))
        assert result == {"env": ["prod"], "labels": ["production"]}

    def test_mixed_with_comma_separated(self) -> None:
        result = parse_tags(("env=prod,staging", "alpha,beta"))
        assert result == {"env": ["prod", "staging"], "labels": ["alpha", "beta"]}


class TestParseTagsEdgeCases:
    """Tests for edge cases."""

    def test_none_returns_none(self) -> None:
        assert parse_tags(None) is None

    def test_empty_tuple_returns_none(self) -> None:
        assert parse_tags(()) is None

    def test_all_empty_segments_returns_none(self) -> None:
        assert parse_tags((",,,",)) is None

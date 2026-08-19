# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Prepare existing Ansible changelog metadata for a selected release version."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_RELEASE_KEY = re.compile(
    r"^  (?P<version>(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)):$"
)
_RST_VERSION = re.compile(
    r"^v(?P<version>(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))$"
)
_INITIAL_SEED = re.compile(
    r"^# sccfm-release-retarget-seed: "
    r"(?P<version>(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))$"
)
_IMMUTABLE_INITIAL_SEED_VERSION = "0.39.0"
_MIN_RST_RELEASE_UNDERLINE = 8
_MAINTAINER_GUIDANCE = "prepare the Ansible changelog in source before releasing"


class AnsibleReleaseError(RuntimeError):
    """Raised when changelog state is unsafe to transform automatically."""


@dataclass(frozen=True)
class AnsibleReleasePreparation:
    """Summary of prepared Ansible release metadata."""

    version: str
    release_date: str
    changed: bool


@dataclass(frozen=True)
class _ReleaseBlock:
    """Line boundaries for one release in changelog.yaml."""

    version: str
    start: int
    end: int


class _UniqueKeyLoader(yaml.SafeLoader):
    """YAML safe loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    """Construct a YAML mapping without silently accepting duplicate keys."""
    loader.flatten_mapping(node)
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key: object = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _validate_version(value: str, label: str) -> None:
    """Require a canonical stable semantic version."""
    if _SEMVER.fullmatch(value) is None:
        raise AnsibleReleaseError(f"{label} must be a canonical stable semantic version")


def _version_tuple(value: str) -> tuple[int, int, int]:
    """Return comparable components for an already validated stable version."""
    major, minor, patch = value.split(".")
    return int(major), int(minor), int(patch)


def _resolved_date(value: str | None) -> str:
    """Return a validated ISO date, defaulting to the current UTC date."""
    resolved = value or datetime.now(timezone.utc).date().isoformat()
    try:
        parsed = date.fromisoformat(resolved)
    except ValueError as exc:
        raise AnsibleReleaseError("release date must be a valid ISO date (YYYY-MM-DD)") from exc
    if _DATE.fullmatch(resolved) is None or parsed.isoformat() != resolved:
        raise AnsibleReleaseError("release date must be a valid ISO date (YYYY-MM-DD)")
    return resolved


def _read_regular_file(path: Path) -> str:
    """Read a required regular file without following a symlink."""
    if path.is_symlink() or not path.is_file():
        raise AnsibleReleaseError(f"required release file is missing or unsafe: {path.name}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AnsibleReleaseError(f"could not read release file: {path.name}") from exc


def _load_releases(content: str) -> dict[str, object]:
    """Load and validate the changelog release mapping."""
    try:
        document: object = yaml.load(content, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise AnsibleReleaseError(f"invalid changelog.yaml; {_MAINTAINER_GUIDANCE}") from exc
    if not isinstance(document, Mapping):
        raise AnsibleReleaseError(f"changelog.yaml is not a mapping; {_MAINTAINER_GUIDANCE}")
    releases: object = document.get("releases")
    if not isinstance(releases, Mapping) or not releases:
        raise AnsibleReleaseError(f"changelog.yaml has no release entries; {_MAINTAINER_GUIDANCE}")
    if any(not isinstance(version, str) for version in releases):
        raise AnsibleReleaseError(
            f"changelog.yaml has invalid release keys; {_MAINTAINER_GUIDANCE}"
        )
    return dict(releases)


def _entry_date(value: object) -> str | None:
    """Return a canonical date from a parsed changelog entry value."""
    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and _DATE.fullmatch(value) is not None:
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return None
    return None


def _validate_entry(raw: object, version: str) -> Mapping[str, object]:
    """Require a complete generated changelog entry without modifying its changes."""
    if not isinstance(raw, Mapping):
        raise AnsibleReleaseError(
            f"release {version} is not a changelog mapping; {_MAINTAINER_GUIDANCE}"
        )
    changes = raw.get("changes")
    fragments = raw.get("fragments")
    if not isinstance(changes, Mapping) or not changes:
        raise AnsibleReleaseError(
            f"release {version} has no recorded changes; {_MAINTAINER_GUIDANCE}"
        )
    if not isinstance(fragments, list) or any(not isinstance(item, str) for item in fragments):
        raise AnsibleReleaseError(
            f"release {version} has invalid fragments; {_MAINTAINER_GUIDANCE}"
        )
    if _entry_date(raw.get("release_date")) is None:
        raise AnsibleReleaseError(
            f"release {version} has an invalid release date; {_MAINTAINER_GUIDANCE}"
        )
    return raw


def _release_blocks(lines: list[str]) -> dict[str, _ReleaseBlock]:
    """Locate unquoted generated release keys for minimal, safe edits."""
    starts: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        match = _RELEASE_KEY.fullmatch(line.rstrip("\n"))
        if match is not None:
            starts.append((match.group("version"), index))
    blocks: dict[str, _ReleaseBlock] = {}
    for position, (version, start) in enumerate(starts):
        end = starts[position + 1][1] if position + 1 < len(starts) else len(lines)
        if version in blocks:
            raise AnsibleReleaseError(f"duplicate release blocks; {_MAINTAINER_GUIDANCE}")
        blocks[version] = _ReleaseBlock(version, start, end)
    return blocks


def _initial_seed_version(lines: list[str]) -> str:
    """Return the one release version explicitly marked as the retargetable seed."""
    versions = [
        match.group("version")
        for line in lines
        if (match := _INITIAL_SEED.fullmatch(line.rstrip("\r\n"))) is not None
    ]
    if len(versions) != 1:
        raise AnsibleReleaseError(
            f"initial release seed is not marked safely; {_MAINTAINER_GUIDANCE}"
        )
    if versions[0] != _IMMUTABLE_INITIAL_SEED_VERSION:
        raise AnsibleReleaseError(
            f"initial release seed marker is not immutable; {_MAINTAINER_GUIDANCE}"
        )
    return versions[0]


def _replace_release_date(lines: list[str], block: _ReleaseBlock, release_date: str) -> None:
    """Replace the one simple release_date scalar in a release block."""
    candidates = [
        index
        for index in range(block.start + 1, block.end)
        if lines[index].startswith("    release_date:")
    ]
    if len(candidates) != 1:
        raise AnsibleReleaseError(f"release date cannot be edited safely; {_MAINTAINER_GUIDANCE}")
    index = candidates[0]
    current = lines[index].rstrip("\n")
    simple_date = re.fullmatch(
        r"    release_date: (?:'(?P<single>[0-9]{4}-[0-9]{2}-[0-9]{2})'|"
        r'"(?P<double>[0-9]{4}-[0-9]{2}-[0-9]{2})"|'
        r"(?P<plain>[0-9]{4}-[0-9]{2}-[0-9]{2}))",
        current,
    )
    if simple_date is None:
        raise AnsibleReleaseError(f"release date cannot be edited safely; {_MAINTAINER_GUIDANCE}")
    if release_date not in simple_date.groups():
        newline = "\n" if lines[index].endswith("\n") else ""
        lines[index] = f"    release_date: '{release_date}'{newline}"


def _retarget_fragments(
    lines: list[str],
    block: _ReleaseBlock,
    fragments: object,
    previous_version: str,
    release_version: str,
) -> None:
    """Retarget only fragment scalars exactly named after the previous version."""
    if not isinstance(fragments, list):
        raise AnsibleReleaseError(f"release fragments cannot be edited; {_MAINTAINER_GUIDANCE}")
    old_name = f"{previous_version}.yml"
    expected = sum(item == old_name for item in fragments)
    patterns = {f"      - {old_name}", f"      - '{old_name}'", f'      - "{old_name}"'}
    candidates = [
        index
        for index in range(block.start + 1, block.end)
        if lines[index].rstrip("\n") in patterns
    ]
    if len(candidates) != expected:
        raise AnsibleReleaseError(
            f"release fragments cannot be edited safely; {_MAINTAINER_GUIDANCE}"
        )
    for index in candidates:
        lines[index] = lines[index].replace(previous_version, release_version, 1)


def _rst_headings(lines: list[str]) -> dict[str, int]:
    """Validate and locate all stable-version RST headings."""
    headings: dict[str, int] = {}
    for index, line in enumerate(lines):
        match = _RST_VERSION.fullmatch(line.rstrip("\n"))
        if match is None:
            continue
        version = match.group("version")
        expected_length = len(f"v{version}")
        underline = lines[index + 1].rstrip("\n") if index + 1 < len(lines) else ""
        if len(underline) < expected_length or set(underline) != {"="}:
            raise AnsibleReleaseError(f"invalid RST release heading; {_MAINTAINER_GUIDANCE}")
        if version in headings:
            raise AnsibleReleaseError(f"duplicate RST release heading; {_MAINTAINER_GUIDANCE}")
        headings[version] = index
    return headings


def _retarget_rst_heading(lines: list[str], index: int, release_version: str) -> None:
    """Retarget one validated RST heading while preserving line endings."""
    heading_newline = "\n" if lines[index].endswith("\n") else ""
    underline_newline = "\n" if lines[index + 1].endswith("\n") else ""
    heading = f"v{release_version}"
    lines[index] = f"{heading}{heading_newline}"
    underline_length = max(len(heading), _MIN_RST_RELEASE_UNDERLINE)
    lines[index + 1] = f"{'=' * underline_length}{underline_newline}"


def _write_changed(path: Path, content: str, original: str) -> bool:
    """Write one changed UTF-8 file and report whether a write occurred."""
    if content == original:
        return False
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise AnsibleReleaseError(f"could not update release file: {path.name}") from exc
    return True


def prepare_ansible_release(
    collection_root: Path,
    previous_version: str,
    release_version: str,
    release_date: str | None = None,
) -> AnsibleReleasePreparation:
    """Align existing collection changelogs with one manually selected version."""
    _validate_version(previous_version, "previous version")
    _validate_version(release_version, "release version")
    if _version_tuple(release_version) <= _version_tuple(previous_version):
        raise AnsibleReleaseError("release version must be greater than previous version")
    resolved_date = _resolved_date(release_date)
    if collection_root.is_symlink() or not collection_root.is_dir():
        raise AnsibleReleaseError("collection root must be a regular directory")

    yaml_path = collection_root / "changelogs" / "changelog.yaml"
    rst_path = collection_root / "CHANGELOG.rst"
    original_yaml = _read_regular_file(yaml_path)
    original_rst = _read_regular_file(rst_path)
    releases = _load_releases(original_yaml)
    if any(_version_tuple(version) > _version_tuple(release_version) for version in releases):
        raise AnsibleReleaseError(
            f"release version must remain the newest changelog entry; {_MAINTAINER_GUIDANCE}"
        )
    yaml_lines = original_yaml.splitlines(keepends=True)
    rst_lines = original_rst.splitlines(keepends=True)
    blocks = _release_blocks(yaml_lines)
    headings = _rst_headings(rst_lines)
    if set(blocks) != set(releases):
        raise AnsibleReleaseError(f"release blocks cannot be edited safely; {_MAINTAINER_GUIDANCE}")
    if set(releases) != set(headings):
        raise AnsibleReleaseError(
            f"changelog files disagree on release history; {_MAINTAINER_GUIDANCE}"
        )

    yaml_has_target = release_version in releases
    rst_has_target = release_version in headings
    if yaml_has_target != rst_has_target:
        raise AnsibleReleaseError(
            f"changelog files disagree on the release; {_MAINTAINER_GUIDANCE}"
        )

    if yaml_has_target:
        seed_version = _initial_seed_version(yaml_lines)
        if release_version != previous_version:
            previous_is_present = previous_version in releases
            consumed_initial_seed = (
                set(releases) == {release_version} and seed_version == previous_version
            )
            if previous_is_present and seed_version == previous_version:
                raise AnsibleReleaseError(
                    f"initial release seed was not retargeted; {_MAINTAINER_GUIDANCE}"
                )
            if not previous_is_present and not consumed_initial_seed:
                raise AnsibleReleaseError(
                    f"previous release is missing from changelog history; {_MAINTAINER_GUIDANCE}"
                )
        _validate_entry(releases[release_version], release_version)
        _replace_release_date(yaml_lines, blocks[release_version], resolved_date)
    else:
        if set(releases) != {previous_version} or set(headings) != {previous_version}:
            raise AnsibleReleaseError(
                f"only a single initial release can be retargeted; {_MAINTAINER_GUIDANCE}"
            )
        if _initial_seed_version(yaml_lines) != previous_version:
            raise AnsibleReleaseError(
                f"initial release seed was already retargeted; {_MAINTAINER_GUIDANCE}"
            )
        entry = _validate_entry(releases[previous_version], previous_version)
        block = blocks[previous_version]
        _replace_release_date(yaml_lines, block, resolved_date)
        _retarget_fragments(
            yaml_lines,
            block,
            entry.get("fragments"),
            previous_version,
            release_version,
        )
        key_newline = "\n" if yaml_lines[block.start].endswith("\n") else ""
        yaml_lines[block.start] = f"  {release_version}:{key_newline}"
        _retarget_rst_heading(rst_lines, headings[previous_version], release_version)

    updated_yaml = "".join(yaml_lines)
    updated_rst = "".join(rst_lines)
    updated_releases = _load_releases(updated_yaml)
    _validate_entry(updated_releases.get(release_version), release_version)
    updated_headings = _rst_headings(rst_lines)
    if release_version not in updated_headings:
        raise AnsibleReleaseError(f"release heading update failed; {_MAINTAINER_GUIDANCE}")

    yaml_changed = _write_changed(yaml_path, updated_yaml, original_yaml)
    rst_changed = _write_changed(rst_path, updated_rst, original_rst)
    return AnsibleReleasePreparation(release_version, resolved_date, yaml_changed or rst_changed)


def _parser() -> argparse.ArgumentParser:
    """Build the release preparation CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("collection_root", type=Path)
    parser.add_argument("--previous-version", required=True)
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--release-date")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare Ansible release metadata from CI or a maintainer shell."""
    args = _parser().parse_args(argv)
    try:
        result = prepare_ansible_release(
            args.collection_root,
            args.previous_version,
            args.release_version,
            args.release_date,
        )
    except AnsibleReleaseError as exc:
        print(f"Ansible release preparation rejected: {exc}", file=sys.stderr)
        return 1
    state = "updated" if result.changed else "already prepared"
    print(f"Ansible changelog {state}: version={result.version} date={result.release_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

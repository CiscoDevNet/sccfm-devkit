# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for preparing manually selected Ansible release metadata."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from cisco_sccfm_scripts.prepare_ansible_release import (
    AnsibleReleaseError,
    main,
    prepare_ansible_release,
)

_INITIAL_VERSION = "0.39.0"
_RELEASE_VERSION = "1.0.0"
_RELEASE_DATE = "2026-08-12"
_SUMMARY = (
    "Initial development release of the cisco.sccfm collection, with dynamic inventory "
    "and modules for automating Cisco Security Cloud Control Firewall Manager."
)


def _yaml_release(
    version: str = _INITIAL_VERSION,
    release_date: str = "2026-07-27",
    fragment: str = "0.39.0.yml",
) -> str:
    return f"""---
ancestor: null
# sccfm-release-retarget-seed: {_INITIAL_VERSION}
releases:
  {version}:
    changes:
      release_summary: {_SUMMARY}
    fragments:
      - {fragment}
    release_date: '{release_date}'
"""


def _rst_release(version: str = _INITIAL_VERSION) -> str:
    heading = f"v{version}"
    return f"""====================================
Cisco SCCFM Collection Release Notes
====================================

.. contents:: Topics

{heading}
{'=' * len(heading)}

Release Summary
---------------

{_SUMMARY}
"""


def _collection(
    tmp_path: Path,
    yaml_content: str | None = None,
    rst_content: str | None = None,
) -> Path:
    root = tmp_path / "sccfm-ansible"
    changelogs = root / "changelogs"
    changelogs.mkdir(parents=True)
    (changelogs / "changelog.yaml").write_text(yaml_content or _yaml_release(), encoding="utf-8")
    (root / "CHANGELOG.rst").write_text(rst_content or _rst_release(), encoding="utf-8")
    return root


def _parsed_release(root: Path, version: str) -> dict[str, object]:
    document = yaml.safe_load((root / "changelogs" / "changelog.yaml").read_text())
    release: object = document["releases"][version]
    assert isinstance(release, dict)
    return release


def test_retargets_only_the_initial_release_metadata(tmp_path: Path) -> None:
    root = _collection(tmp_path)

    result = prepare_ansible_release(
        root,
        _INITIAL_VERSION,
        _RELEASE_VERSION,
        _RELEASE_DATE,
    )

    assert result.version == _RELEASE_VERSION
    assert result.release_date == _RELEASE_DATE
    assert result.changed
    release = _parsed_release(root, _RELEASE_VERSION)
    assert release["release_date"] == _RELEASE_DATE
    assert release["fragments"] == ["1.0.0.yml"]
    assert release["changes"] == {"release_summary": _SUMMARY}
    rst = (root / "CHANGELOG.rst").read_text(encoding="utf-8")
    assert "v1.0.0\n========" in rst
    assert "v0.39.0" not in rst
    assert _SUMMARY in rst


def test_checked_in_changelog_supports_initial_and_later_releases(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    source = repository / "sccfm-ansible"
    root = tmp_path / "sccfm-ansible"
    (root / "changelogs").mkdir(parents=True)
    shutil.copy2(source / "changelogs" / "changelog.yaml", root / "changelogs")
    shutil.copy2(source / "CHANGELOG.rst", root)

    checked_in_versions = set(
        yaml.safe_load((root / "changelogs" / "changelog.yaml").read_text())["releases"]
    )
    versions = sorted(
        checked_in_versions,
        key=lambda version: tuple(int(part) for part in version.split(".")),
    )
    is_unprepared_seed = versions == [_INITIAL_VERSION]
    if is_unprepared_seed:
        previous_version = _INITIAL_VERSION
        release_version = _RELEASE_VERSION
        release_date = _RELEASE_DATE
        expected_versions = {_RELEASE_VERSION}
    else:
        previous_version = versions[-2] if len(versions) > 1 else _INITIAL_VERSION
        release_version = versions[-1]
        checked_in_date = _parsed_release(root, release_version)["release_date"]
        assert isinstance(checked_in_date, str)
        release_date = checked_in_date
        expected_versions = checked_in_versions

    result = prepare_ansible_release(
        root,
        previous_version,
        release_version,
        release_date,
    )

    assert result.changed is is_unprepared_seed
    assert (
        set(yaml.safe_load((root / "changelogs" / "changelog.yaml").read_text())["releases"])
        == expected_versions
    )
    assert f"v{release_version}" in (root / "CHANGELOG.rst").read_text(encoding="utf-8")


def test_preserves_a_fragment_not_named_after_the_previous_version(tmp_path: Path) -> None:
    root = _collection(tmp_path, yaml_content=_yaml_release(fragment="initial-release.yml"))

    prepare_ansible_release(root, _INITIAL_VERSION, _RELEASE_VERSION, _RELEASE_DATE)

    assert _parsed_release(root, _RELEASE_VERSION)["fragments"] == ["initial-release.yml"]


def test_an_already_prepared_release_is_idempotent(tmp_path: Path) -> None:
    root = _collection(tmp_path)
    prepare_ansible_release(root, _INITIAL_VERSION, _RELEASE_VERSION, _RELEASE_DATE)
    yaml_before = (root / "changelogs" / "changelog.yaml").read_bytes()
    rst_before = (root / "CHANGELOG.rst").read_bytes()

    result = prepare_ansible_release(
        root,
        _INITIAL_VERSION,
        _RELEASE_VERSION,
        _RELEASE_DATE,
    )

    assert not result.changed
    assert (root / "changelogs" / "changelog.yaml").read_bytes() == yaml_before
    assert (root / "CHANGELOG.rst").read_bytes() == rst_before


def test_an_already_prepared_release_only_updates_its_date(tmp_path: Path) -> None:
    root = _collection(tmp_path)
    prepare_ansible_release(root, _INITIAL_VERSION, _RELEASE_VERSION, "2026-08-01")
    rst_before = (root / "CHANGELOG.rst").read_bytes()

    result = prepare_ansible_release(
        root,
        _INITIAL_VERSION,
        _RELEASE_VERSION,
        _RELEASE_DATE,
    )

    assert result.changed
    assert _parsed_release(root, _RELEASE_VERSION)["release_date"] == _RELEASE_DATE
    assert (root / "CHANGELOG.rst").read_bytes() == rst_before


def test_accepts_an_existing_target_among_historical_releases(tmp_path: Path) -> None:
    first = _yaml_release("0.9.0", "2026-07-01", "0.9.0.yml")
    second = _yaml_release(_RELEASE_VERSION, _RELEASE_DATE, "1.0.0.yml").split(
        "releases:\n", maxsplit=1
    )[1]
    yaml_content = first + second
    rst_content = (
        _rst_release(_RELEASE_VERSION)
        + "\n"
        + _rst_release("0.9.0").split(".. contents:: Topics\n", maxsplit=1)[1].lstrip()
    )
    root = _collection(tmp_path, yaml_content=yaml_content, rst_content=rst_content)

    result = prepare_ansible_release(root, "0.9.0", _RELEASE_VERSION, _RELEASE_DATE)

    assert not result.changed


def test_rejects_a_target_that_replaced_published_history_without_writing(
    tmp_path: Path,
) -> None:
    root = _collection(
        tmp_path,
        yaml_content=_yaml_release("2.0.0", _RELEASE_DATE, "2.0.0.yml"),
        rst_content=_rst_release("2.0.0"),
    )
    yaml_path = root / "changelogs" / "changelog.yaml"
    rst_path = root / "CHANGELOG.rst"
    before = (yaml_path.read_bytes(), rst_path.read_bytes())

    with pytest.raises(AnsibleReleaseError, match="previous release is missing.*prepare"):
        prepare_ansible_release(root, _RELEASE_VERSION, "2.0.0", _RELEASE_DATE)

    assert (yaml_path.read_bytes(), rst_path.read_bytes()) == before


def test_rejects_an_unconsumed_seed_alongside_the_first_target(tmp_path: Path) -> None:
    target = _yaml_release(_RELEASE_VERSION, _RELEASE_DATE, "1.0.0.yml").split(
        "releases:\n", maxsplit=1
    )[1]
    target_rst = (
        _rst_release(_RELEASE_VERSION).split(".. contents:: Topics\n", maxsplit=1)[1].lstrip()
    )
    root = _collection(
        tmp_path,
        yaml_content=_yaml_release() + target,
        rst_content=_rst_release() + "\n" + target_rst,
    )

    with pytest.raises(AnsibleReleaseError, match="seed was not retargeted.*prepare"):
        prepare_ansible_release(root, _INITIAL_VERSION, _RELEASE_VERSION, _RELEASE_DATE)


def test_second_release_cannot_retarget_and_erase_published_history(tmp_path: Path) -> None:
    root = _collection(tmp_path)
    prepare_ansible_release(root, _INITIAL_VERSION, _RELEASE_VERSION, _RELEASE_DATE)
    yaml_path = root / "changelogs" / "changelog.yaml"
    rst_path = root / "CHANGELOG.rst"
    before = (yaml_path.read_bytes(), rst_path.read_bytes())

    with pytest.raises(AnsibleReleaseError, match="seed was already retargeted.*prepare"):
        prepare_ansible_release(root, _RELEASE_VERSION, "2.0.0", "2026-09-01")

    assert (yaml_path.read_bytes(), rst_path.read_bytes()) == before
    assert set(yaml.safe_load(yaml_path.read_text())["releases"]) == {_RELEASE_VERSION}
    assert f"v{_RELEASE_VERSION}" in rst_path.read_text(encoding="utf-8")


def test_moved_seed_marker_cannot_authorize_history_retarget(tmp_path: Path) -> None:
    yaml_content = _yaml_release(_RELEASE_VERSION).replace(
        f"sccfm-release-retarget-seed: {_INITIAL_VERSION}",
        f"sccfm-release-retarget-seed: {_RELEASE_VERSION}",
    )
    root = _collection(
        tmp_path,
        yaml_content=yaml_content,
        rst_content=_rst_release(_RELEASE_VERSION),
    )
    before = (
        (root / "changelogs" / "changelog.yaml").read_bytes(),
        (root / "CHANGELOG.rst").read_bytes(),
    )

    with pytest.raises(AnsibleReleaseError, match="seed marker is not immutable"):
        prepare_ansible_release(root, _RELEASE_VERSION, "2.0.0", "2026-09-01")

    assert (
        (root / "changelogs" / "changelog.yaml").read_bytes(),
        (root / "CHANGELOG.rst").read_bytes(),
    ) == before


@pytest.mark.parametrize(
    "version",
    ["01.2.3", "1.02.3", "1.2.03", "v1.2.3", "1.2", "1.2.3-rc.1", "1.2.3+1"],
)
def test_rejects_noncanonical_or_unstable_versions(tmp_path: Path, version: str) -> None:
    root = _collection(tmp_path)

    with pytest.raises(AnsibleReleaseError, match="canonical stable semantic version"):
        prepare_ansible_release(root, _INITIAL_VERSION, version, _RELEASE_DATE)


@pytest.mark.parametrize("release_version", ["0.39.0", "0.38.9"])
def test_rejects_non_increasing_release_versions(
    tmp_path: Path,
    release_version: str,
) -> None:
    root = _collection(tmp_path)

    with pytest.raises(AnsibleReleaseError, match="greater than previous"):
        prepare_ansible_release(root, _INITIAL_VERSION, release_version, _RELEASE_DATE)


def test_rejects_release_when_changelog_contains_a_newer_entry(tmp_path: Path) -> None:
    target = _yaml_release("1.0.0", _RELEASE_DATE, "1.0.0.yml")
    future = _yaml_release("2.0.0", "2026-09-01", "2.0.0.yml").split("releases:\n", maxsplit=1)[1]
    future_rst = _rst_release("2.0.0").split(".. contents:: Topics\n", maxsplit=1)[1].lstrip()
    root = _collection(
        tmp_path,
        yaml_content=target + future,
        rst_content=_rst_release("1.0.0") + "\n" + future_rst,
    )

    with pytest.raises(AnsibleReleaseError, match="newest changelog entry"):
        prepare_ansible_release(root, "0.9.0", "1.0.0", _RELEASE_DATE)


@pytest.mark.parametrize("release_date", ["2026-02-29", "2026-8-12", "12-08-2026"])
def test_rejects_invalid_release_dates(tmp_path: Path, release_date: str) -> None:
    root = _collection(tmp_path)

    with pytest.raises(AnsibleReleaseError, match="valid ISO date"):
        prepare_ansible_release(root, _INITIAL_VERSION, _RELEASE_VERSION, release_date)


def test_rejects_mixed_yaml_and_rst_versions_without_writing(tmp_path: Path) -> None:
    root = _collection(tmp_path, rst_content=_rst_release(_RELEASE_VERSION))
    yaml_path = root / "changelogs" / "changelog.yaml"
    rst_path = root / "CHANGELOG.rst"
    before = (yaml_path.read_bytes(), rst_path.read_bytes())

    with pytest.raises(AnsibleReleaseError, match="disagree.*prepare the Ansible changelog"):
        prepare_ansible_release(root, _INITIAL_VERSION, _RELEASE_VERSION, _RELEASE_DATE)

    assert (yaml_path.read_bytes(), rst_path.read_bytes()) == before


def test_rejects_multiple_initial_entries_without_writing(tmp_path: Path) -> None:
    extra = _yaml_release("0.37.0", "2026-06-01", "0.37.0.yml").split("releases:\n", maxsplit=1)[1]
    extra_rst = _rst_release("0.37.0").split(".. contents:: Topics\n", maxsplit=1)[1].lstrip()
    root = _collection(
        tmp_path,
        yaml_content=_yaml_release() + extra,
        rst_content=_rst_release() + "\n" + extra_rst,
    )
    yaml_path = root / "changelogs" / "changelog.yaml"
    before = yaml_path.read_bytes()

    with pytest.raises(AnsibleReleaseError, match="single initial release.*prepare"):
        prepare_ansible_release(root, _INITIAL_VERSION, _RELEASE_VERSION, _RELEASE_DATE)

    assert yaml_path.read_bytes() == before


def test_rejects_malformed_rst_release_heading(tmp_path: Path) -> None:
    malformed = _rst_release().replace("v0.39.0\n=======\n", "v0.39.0\n======\n")
    root = _collection(tmp_path, rst_content=malformed)

    with pytest.raises(AnsibleReleaseError, match="invalid RST release heading.*prepare"):
        prepare_ansible_release(root, _INITIAL_VERSION, _RELEASE_VERSION, _RELEASE_DATE)


def test_accepts_rst_release_underline_longer_than_heading(tmp_path: Path) -> None:
    rst_content = _rst_release().replace("v0.39.0\n=======\n", "v0.39.0\n========\n")
    root = _collection(tmp_path, rst_content=rst_content)

    result = prepare_ansible_release(
        root,
        _INITIAL_VERSION,
        _RELEASE_VERSION,
        _RELEASE_DATE,
    )

    assert result.changed


def test_rejects_duplicate_yaml_keys(tmp_path: Path) -> None:
    yaml_content = _yaml_release().replace(
        "    release_date: '2026-07-27'",
        "    release_date: '2026-07-27'\n    release_date: '2026-07-28'",
    )
    root = _collection(tmp_path, yaml_content=yaml_content)

    with pytest.raises(AnsibleReleaseError, match="invalid changelog.yaml.*prepare"):
        prepare_ansible_release(root, _INITIAL_VERSION, _RELEASE_VERSION, _RELEASE_DATE)


def test_cli_reports_success_and_validation_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _collection(tmp_path)

    success = main(
        [
            str(root),
            "--previous-version",
            _INITIAL_VERSION,
            "--release-version",
            _RELEASE_VERSION,
            "--release-date",
            _RELEASE_DATE,
        ]
    )
    failure = main(
        [
            str(root),
            "--previous-version",
            _INITIAL_VERSION,
            "--release-version",
            "not-a-version",
        ]
    )

    captured = capsys.readouterr()
    assert success == 0
    assert failure == 1
    assert "Ansible changelog updated" in captured.out
    assert "canonical stable semantic version" in captured.err

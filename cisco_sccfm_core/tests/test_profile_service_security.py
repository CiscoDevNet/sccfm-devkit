# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any, TextIO

import pytest

from cisco_sccfm_core.models.profile import Profile
from cisco_sccfm_core.services import ProfileService
from cisco_sccfm_core.services import profile_service as profile_service_module

POSIX_ONLY = pytest.mark.skipif(
    os.name != "posix",
    reason="POSIX permission bits are not portable to this platform",
)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _temporary_files(config_path: Path) -> list[Path]:
    return list(config_path.parent.glob(f".{config_path.name}.*.tmp"))


def _write_config(path: Path, profile: str = "default") -> Profile:
    expected = Profile(profile=profile, region="us", api_token="example-token")
    path.write_text(
        json.dumps(
            {
                "profiles": {
                    profile: {
                        "region": expected.region,
                        "api_token": expected.api_token,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return expected


def _use_default_path(monkeypatch: pytest.MonkeyPatch, config_path: Path) -> None:
    monkeypatch.setattr(profile_service_module, "_CONFIG_DIR", config_path.parent)
    monkeypatch.setattr(profile_service_module, "_CONFIG_FILE", config_path)


def test_should_save_and_load_config(tmp_path: Path) -> None:
    """ProfileService should persist and retrieve configuration."""
    config_path = tmp_path / "config.json"
    service = ProfileService(path=config_path)

    expected = Profile(profile="default", region="us", api_token="secret-token")
    service.save(expected)

    loaded = service.load("default")
    assert loaded == expected


def test_should_list_all_profiles(tmp_path: Path) -> None:
    """ProfileService should list all saved profiles."""
    config_path = tmp_path / "config.json"
    service = ProfileService(path=config_path)

    expected = Profile(profile="default", region="us", api_token="secret-token")
    service.save(expected)

    profiles = service.list_profiles()
    assert profiles == [expected]


def test_load_rejects_directory_without_changing_it(tmp_path: Path) -> None:
    """A directory passed as the config path must be rejected before hardening."""
    config_path = tmp_path / "config.json"
    config_path.mkdir()
    original_mode = _mode(config_path)

    with pytest.raises(ValueError, match="regular file"):
        ProfileService(path=config_path).load("default")

    assert _mode(config_path) == original_mode


def test_load_rejects_configuration_file_symlink(tmp_path: Path) -> None:
    """Loading must not follow or chmod a symlink supplied as the config path."""
    target_path = tmp_path / "target.json"
    expected = _write_config(target_path)
    config_path = tmp_path / "config.json"
    config_path.symlink_to(target_path)
    original_mode = _mode(target_path)

    with pytest.raises(ValueError, match="symbolic link"):
        ProfileService(path=config_path).load(expected.profile)

    assert _mode(target_path) == original_mode


def test_save_rejects_configuration_directory_symlink(tmp_path: Path) -> None:
    """Saving must not follow or chmod a symlink supplied as the config directory."""
    target_directory = tmp_path / "target"
    target_directory.mkdir()
    config_directory = tmp_path / "linked"
    config_directory.symlink_to(target_directory, target_is_directory=True)
    original_mode = _mode(target_directory)

    with pytest.raises(ValueError, match="must not contain symbolic links"):
        ProfileService(path=config_directory / "config.json").save(
            Profile(profile="default", region="us", api_token="example-token")
        )

    assert not (target_directory / "config.json").exists()
    assert _mode(target_directory) == original_mode


@pytest.mark.parametrize(
    ("provided", "normalized"),
    [
        (Path("/tmp/sccfm/config.json"), Path("/private/tmp/sccfm/config.json")),
        (Path("/var/sccfm/config.json"), Path("/private/var/sccfm/config.json")),
    ],
)
def test_macos_fixed_directory_aliases_are_normalized(
    provided: Path,
    normalized: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only macOS's fixed /tmp and /var aliases should use their physical paths."""
    monkeypatch.setattr(profile_service_module.sys, "platform", "darwin")

    service = ProfileService(path=provided)

    assert service._path == normalized


@pytest.mark.parametrize(
    "path",
    [
        Path("/private/tmp/sccfm/config.json"),
        Path("/opt/tmp/sccfm/config.json"),
        Path("relative/tmp/sccfm/config.json"),
    ],
)
def test_macos_path_normalization_is_narrow(
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalization must not resolve or rewrite arbitrary path components."""
    monkeypatch.setattr(profile_service_module.sys, "platform", "darwin")

    service = ProfileService(path=path)

    assert service._path == path


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS fixed aliases are platform-specific")
def test_macos_alias_normalization_still_rejects_user_controlled_symlink(
    tmp_path: Path,
) -> None:
    """Allowing the fixed /var alias must not allow a later user-created symlink."""
    if tmp_path.parts[1:3] != ("private", "var"):
        pytest.skip("pytest temporary storage is not below macOS /private/var")
    target_directory = tmp_path / "target"
    target_directory.mkdir()
    linked_directory = tmp_path / "linked"
    linked_directory.symlink_to(target_directory, target_is_directory=True)
    alias_root = Path(tmp_path.anchor).joinpath(*tmp_path.parts[2:])

    with pytest.raises(ValueError, match="must not contain symbolic links"):
        ProfileService(path=alias_root / "linked" / "config.json").save(
            Profile(profile="default", region="us", api_token="example-token")
        )

    assert not (target_directory / "config.json").exists()


def test_save_validates_opened_file_before_updating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A descriptor rejected after open must retain its existing payload."""
    config_path = tmp_path / "config.json"
    original_payload = "must-not-be-truncated"
    config_path.write_text(original_payload, encoding="utf-8")
    service = ProfileService(path=config_path)

    def reject_descriptor(
        descriptor: int,
        *,
        parent_descriptor: int | None = None,
    ) -> None:
        raise ValueError("synthetic non-regular descriptor")

    monkeypatch.setattr(service, "_ensure_regular_descriptor", reject_descriptor)

    with pytest.raises(ValueError, match="synthetic non-regular"):
        service.save(Profile(profile="default", region="us", api_token="example-token"))

    assert config_path.read_text(encoding="utf-8") == original_payload


@pytest.mark.parametrize("payload", ["", "{malformed-json"])
def test_save_preserves_invalid_existing_payload_before_rewrite(
    tmp_path: Path,
    payload: str,
) -> None:
    """Empty or malformed existing storage must not be mistaken for a new file."""
    config_path = tmp_path / "config.json"
    config_path.write_text(payload, encoding="utf-8")
    if os.name == "posix":
        config_path.chmod(0o644)

    with pytest.raises(json.JSONDecodeError):
        ProfileService(path=config_path).save(
            Profile(profile="default", region="us", api_token="example-token")
        )

    assert config_path.read_text(encoding="utf-8") == payload
    if os.name == "posix":
        assert _mode(config_path) == 0o600


@POSIX_ONLY
def test_save_preserves_existing_config_when_serialization_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A serialization failure must leave the installed configuration untouched."""
    config_path = tmp_path / "config.json"
    _write_config(config_path, profile="existing")
    config_path.chmod(0o600)
    original_payload = config_path.read_bytes()

    def fail_dump(payload: Any, handle: TextIO, *, indent: int) -> None:
        raise TypeError("synthetic serialization failure")

    monkeypatch.setattr(profile_service_module.json, "dump", fail_dump)

    with pytest.raises(TypeError, match="synthetic serialization failure"):
        ProfileService(path=config_path).save(
            Profile(profile="added", region="eu", api_token="must-not-be-installed")
        )

    assert config_path.read_bytes() == original_payload
    assert _temporary_files(config_path) == []


@POSIX_ONLY
def test_save_preserves_existing_config_after_partial_temporary_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial temporary write must not corrupt or replace live configuration."""
    config_path = tmp_path / "config.json"
    _write_config(config_path, profile="existing")
    config_path.chmod(0o600)
    original_payload = config_path.read_bytes()

    def fail_dump(payload: Any, handle: TextIO, *, indent: int) -> None:
        handle.write('{"profiles":')
        raise OSError("synthetic write failure")

    monkeypatch.setattr(profile_service_module.json, "dump", fail_dump)

    with pytest.raises(OSError, match="synthetic write failure"):
        ProfileService(path=config_path).save(
            Profile(profile="added", region="eu", api_token="must-not-be-installed")
        )

    assert config_path.read_bytes() == original_payload
    assert _temporary_files(config_path) == []


@POSIX_ONLY
def test_save_preserves_existing_config_when_temporary_fsync_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A temporary-file fsync failure must abort before replacing live configuration."""
    config_path = tmp_path / "config.json"
    _write_config(config_path, profile="existing")
    config_path.chmod(0o600)
    original_payload = config_path.read_bytes()
    real_fsync = os.fsync

    def fail_regular_file_fsync(descriptor: int) -> None:
        if stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("synthetic fsync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(profile_service_module.os, "fsync", fail_regular_file_fsync)

    with pytest.raises(OSError, match="synthetic fsync failure"):
        ProfileService(path=config_path).save(
            Profile(profile="added", region="eu", api_token="must-not-be-installed")
        )

    assert config_path.read_bytes() == original_payload
    assert _temporary_files(config_path) == []


@POSIX_ONLY
def test_save_syncs_temporary_file_and_parent_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful atomic save must make both content and replacement durable."""
    config_path = tmp_path / "config.json"
    real_fsync = os.fsync
    synced_modes: list[int] = []

    def observe_fsync(descriptor: int) -> None:
        synced_modes.append(os.fstat(descriptor).st_mode)
        real_fsync(descriptor)

    monkeypatch.setattr(profile_service_module.os, "fsync", observe_fsync)

    ProfileService(path=config_path).save(
        Profile(profile="default", region="us", api_token="example-token")
    )

    assert len(synced_modes) == 2
    assert stat.S_ISREG(synced_modes[0])
    assert stat.S_ISDIR(synced_modes[1])
    assert _temporary_files(config_path) == []


@POSIX_ONLY
def test_save_uses_descriptor_relative_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The final replace must stay anchored to the validated parent descriptor."""
    config_path = tmp_path / "config.json"
    real_replace = os.replace
    replace_descriptors: list[tuple[int | None, int | None]] = []

    def observe_replace(
        source: str | os.PathLike[str],
        destination: str | os.PathLike[str],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        replace_descriptors.append((src_dir_fd, dst_dir_fd))
        real_replace(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(profile_service_module.os, "replace", observe_replace)

    ProfileService(path=config_path).save(
        Profile(profile="default", region="us", api_token="example-token")
    )

    assert len(replace_descriptors) == 1
    source_descriptor, destination_descriptor = replace_descriptors[0]
    assert source_descriptor is not None
    assert source_descriptor == destination_descriptor


@POSIX_ONLY
def test_save_rejects_path_swap_before_atomic_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replacing a path after open must not truncate either regular file."""
    config_path = tmp_path / "config.json"
    opened_path = tmp_path / "opened.json"
    replacement_path = tmp_path / "replacement.json"
    original_payload = "opened-file-payload"
    replacement_payload = "replacement-file-payload"
    config_path.write_text(original_payload, encoding="utf-8")
    replacement_path.write_text(replacement_payload, encoding="utf-8")
    real_open = os.open
    swapped = False

    def swap_after_open(
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        is_config_open = Path(path) in (config_path, Path(config_path.name))
        if is_config_open and dir_fd is not None and not flags & os.O_CREAT and not swapped:
            config_path.rename(opened_path)
            replacement_path.rename(config_path)
            swapped = True
        return descriptor

    monkeypatch.setattr(profile_service_module.os, "open", swap_after_open)

    with pytest.raises(ValueError, match="changed while being opened"):
        ProfileService(path=config_path).save(
            Profile(profile="added", region="eu", api_token="must-not-be-written")
        )

    assert opened_path.read_text(encoding="utf-8") == original_payload
    assert config_path.read_text(encoding="utf-8") == replacement_payload


@POSIX_ONLY
def test_read_rejects_parent_swap_without_reading_attacker_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parent replacement must not redirect a readonly profile open."""
    config_parent = tmp_path / "config-parent"
    config_parent.mkdir()
    config_path = config_parent / "config.json"
    original = _write_config(config_path)
    config_path.chmod(0o600)
    original_payload = config_path.read_text(encoding="utf-8")

    attacker_parent = tmp_path / "attacker-parent"
    attacker_parent.mkdir()
    attacker_path = attacker_parent / "config.json"
    attacker_secret = "attacker-profile-secret"
    attacker_path.write_text(attacker_secret, encoding="utf-8")
    attacker_path.chmod(0o600)
    moved_parent = tmp_path / "original-parent"
    real_open = os.open
    swapped = False

    def swap_parent_before_relative_open(
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if Path(path) == Path(config_path.name) and dir_fd is not None and not swapped:
            config_parent.rename(moved_parent)
            config_parent.symlink_to(attacker_parent, target_is_directory=True)
            swapped = True
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(profile_service_module.os, "open", swap_parent_before_relative_open)

    with pytest.raises(ValueError, match="directory changed") as excinfo:
        ProfileService(path=config_path).load(original.profile)

    assert original.api_token not in str(excinfo.value)
    assert attacker_secret not in str(excinfo.value)
    assert (moved_parent / "config.json").read_text(encoding="utf-8") == original_payload
    assert attacker_path.read_text(encoding="utf-8") == attacker_secret


@POSIX_ONLY
def test_save_rejects_parent_swap_without_redirecting_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parent replacement must not redirect an explicit profile update."""
    config_parent = tmp_path / "config-parent"
    config_parent.mkdir()
    config_path = config_parent / "config.json"
    _write_config(config_path, profile="existing")
    config_path.chmod(0o600)
    original_payload = config_path.read_text(encoding="utf-8")

    attacker_parent = tmp_path / "attacker-parent"
    attacker_parent.mkdir()
    attacker_path = attacker_parent / "config.json"
    attacker_payload = "attacker-owned-payload"
    attacker_path.write_text(attacker_payload, encoding="utf-8")
    attacker_path.chmod(0o600)
    moved_parent = tmp_path / "original-parent"
    new_secret = "must-not-be-redirected"
    real_open = os.open
    swapped = False

    def swap_parent_before_relative_open(
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if Path(path) == Path(config_path.name) and dir_fd is not None and not swapped:
            config_parent.rename(moved_parent)
            config_parent.symlink_to(attacker_parent, target_is_directory=True)
            swapped = True
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(profile_service_module.os, "open", swap_parent_before_relative_open)

    with pytest.raises(ValueError, match="directory changed") as excinfo:
        ProfileService(path=config_path).save(
            Profile(profile="added", region="eu", api_token=new_secret)
        )

    assert new_secret not in str(excinfo.value)
    assert new_secret not in (moved_parent / "config.json").read_text(encoding="utf-8")
    assert (moved_parent / "config.json").read_text(encoding="utf-8") == original_payload
    assert attacker_path.read_text(encoding="utf-8") == attacker_payload


@POSIX_ONLY
def test_read_rejects_intermediate_ancestor_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A validated ancestor cannot be replaced before the readonly open."""
    trusted_root = tmp_path / "trusted"
    config_parent = trusted_root / "config-parent"
    config_parent.mkdir(parents=True)
    config_path = config_parent / "config.json"
    original = _write_config(config_path)
    config_path.chmod(0o600)
    original_payload = config_path.read_text(encoding="utf-8")

    attacker_root = tmp_path / "attacker-root"
    attacker_parent = attacker_root / "config-parent"
    attacker_parent.mkdir(parents=True)
    attacker_path = attacker_parent / "config.json"
    attacker = _write_config(attacker_path, profile="attacker")
    attacker_path.chmod(0o600)
    attacker_payload = attacker_path.read_text(encoding="utf-8")
    moved_root = tmp_path / "original-trusted"
    service = ProfileService(path=config_path)
    original_validate = service._validate_configuration_file
    swapped = False

    def validate_then_swap_ancestor() -> None:
        nonlocal swapped
        original_validate()
        if not swapped:
            trusted_root.rename(moved_root)
            trusted_root.symlink_to(attacker_root, target_is_directory=True)
            swapped = True

    monkeypatch.setattr(service, "_validate_configuration_file", validate_then_swap_ancestor)

    with pytest.raises(ValueError, match="changed|symbolic") as excinfo:
        service.load(original.profile)

    assert original.api_token not in str(excinfo.value)
    assert attacker.api_token not in str(excinfo.value)
    assert (moved_root / "config-parent" / "config.json").read_text(
        encoding="utf-8"
    ) == original_payload
    assert attacker_path.read_text(encoding="utf-8") == attacker_payload


@POSIX_ONLY
def test_save_rejects_intermediate_ancestor_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A validated ancestor cannot redirect an explicit profile update."""
    trusted_root = tmp_path / "trusted"
    config_parent = trusted_root / "config-parent"
    config_parent.mkdir(parents=True)
    config_path = config_parent / "config.json"
    _write_config(config_path, profile="existing")
    config_path.chmod(0o600)
    original_payload = config_path.read_text(encoding="utf-8")

    attacker_root = tmp_path / "attacker-root"
    attacker_parent = attacker_root / "config-parent"
    attacker_parent.mkdir(parents=True)
    attacker_path = attacker_parent / "config.json"
    _write_config(attacker_path, profile="attacker")
    attacker_path.chmod(0o600)
    attacker_payload = attacker_path.read_text(encoding="utf-8")
    moved_root = tmp_path / "original-trusted"
    new_secret = "must-not-reach-either-file"
    service = ProfileService(path=config_path)
    original_validate = service._validate_configuration_file
    validations = 0

    def validate_then_swap_ancestor() -> None:
        nonlocal validations
        original_validate()
        validations += 1
        if validations == 2:
            trusted_root.rename(moved_root)
            trusted_root.symlink_to(attacker_root, target_is_directory=True)

    monkeypatch.setattr(service, "_validate_configuration_file", validate_then_swap_ancestor)

    with pytest.raises(ValueError, match="changed|symbolic") as excinfo:
        service.save(Profile(profile="added", region="eu", api_token=new_secret))

    original_after = (moved_root / "config-parent" / "config.json").read_text(encoding="utf-8")
    assert new_secret not in str(excinfo.value)
    assert new_secret not in original_after
    assert new_secret not in attacker_path.read_text(encoding="utf-8")
    assert original_after == original_payload
    assert attacker_path.read_text(encoding="utf-8") == attacker_payload


@POSIX_ONLY
def test_load_does_not_write_file_or_directory_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A readonly load must not call chmod even when modes are already safe."""
    config_path = tmp_path / ".sccfm-cli" / "config.json"
    config_path.parent.mkdir()
    config_path.parent.chmod(0o700)
    expected = _write_config(config_path)
    config_path.chmod(0o600)
    _use_default_path(monkeypatch, config_path)

    def reject_fchmod(descriptor: int, mode: int) -> None:
        pytest.fail(f"os.fchmod was called for descriptor {descriptor} with mode {mode:o}")

    monkeypatch.setattr(profile_service_module.os, "fchmod", reject_fchmod)

    assert ProfileService().load(expected.profile) == expected
    assert _mode(config_path.parent) == 0o700
    assert _mode(config_path) == 0o600


@POSIX_ONLY
def test_new_custom_storage_is_private_before_payload_is_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """New custom storage should be private as soon as its payload is written."""
    config_path = tmp_path / "custom" / "config.json"
    original_dump = json.dump
    modes_during_write: list[int] = []

    def observe_mode(payload: Any, handle: TextIO, *, indent: int) -> None:
        modes_during_write.append(stat.S_IMODE(os.fstat(handle.fileno()).st_mode))
        original_dump(payload, handle, indent=indent)

    monkeypatch.setattr(profile_service_module.json, "dump", observe_mode)

    ProfileService(path=config_path).save(
        Profile(profile="default", region="us", api_token="example-token")
    )

    assert modes_during_write == [0o600]
    assert _mode(config_path.parent) == 0o700
    assert _mode(config_path) == 0o600


@POSIX_ONLY
def test_new_default_storage_is_private(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default config directory and file should be private when created."""
    config_path = tmp_path / ".sccfm-cli" / "config.json"
    _use_default_path(monkeypatch, config_path)

    ProfileService().save(Profile(profile="default", region="us", api_token="example-token"))

    assert _mode(config_path.parent) == 0o700
    assert _mode(config_path) == 0o600


@POSIX_ONLY
@pytest.mark.parametrize("unsafe_mode", [0o000, 0o400, 0o640, 0o644, 0o660, 0o700])
def test_load_rejects_unsafe_custom_file_without_changing_modes(
    tmp_path: Path,
    unsafe_mode: int,
) -> None:
    """Custom profile reads require 0600 and must not repair the file or parent."""
    custom_parent = tmp_path / "shared-config"
    custom_parent.mkdir()
    custom_parent.chmod(0o750)
    config_path = custom_parent / "config.json"
    expected = _write_config(config_path)
    config_path.chmod(unsafe_mode)

    expected_mode = f"{unsafe_mode:04o}"
    with pytest.raises(PermissionError, match=f"expected 0600, found {expected_mode}") as excinfo:
        ProfileService(path=config_path).load(expected.profile)

    assert expected.api_token not in str(excinfo.value)
    assert "sccfm-cli configure" in str(excinfo.value)
    assert _mode(config_path) == unsafe_mode
    assert _mode(custom_parent) == 0o750


@POSIX_ONLY
def test_save_repairs_custom_file_and_preserves_profiles_without_changing_parent(
    tmp_path: Path,
) -> None:
    """Explicit save may repair a custom file while preserving its other profiles."""
    custom_parent = tmp_path / "shared-config"
    custom_parent.mkdir()
    custom_parent.chmod(0o750)
    config_path = custom_parent / "config.json"
    existing = _write_config(config_path, profile="existing")
    config_path.chmod(0o644)
    original_inode = config_path.stat().st_ino
    added = Profile(profile="added", region="eu", api_token="another-example-token")

    service = ProfileService(path=config_path)
    service.save(added)

    assert config_path.stat().st_ino != original_inode
    assert _mode(config_path) == 0o600
    assert _mode(custom_parent) == 0o750
    assert service.load(existing.profile) == existing
    assert service.load(added.profile) == added


@POSIX_ONLY
def test_load_rejects_unsafe_default_directory_without_changing_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default profile reads require 0700 on the directory and never repair it."""
    config_path = tmp_path / ".sccfm-cli" / "config.json"
    config_path.parent.mkdir()
    config_path.parent.chmod(0o755)
    expected = _write_config(config_path)
    config_path.chmod(0o600)
    _use_default_path(monkeypatch, config_path)

    with pytest.raises(PermissionError, match="expected 0700, found 0755"):
        ProfileService().load(expected.profile)

    assert _mode(config_path.parent) == 0o755
    assert _mode(config_path) == 0o600


@POSIX_ONLY
def test_load_rejects_unsafe_default_file_without_changing_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default profile reads require 0600 on the file and never repair it."""
    config_path = tmp_path / ".sccfm-cli" / "config.json"
    config_path.parent.mkdir()
    config_path.parent.chmod(0o700)
    expected = _write_config(config_path)
    config_path.chmod(0o640)
    _use_default_path(monkeypatch, config_path)

    with pytest.raises(PermissionError, match="expected 0600, found 0640"):
        ProfileService().load(expected.profile)

    assert _mode(config_path.parent) == 0o700
    assert _mode(config_path) == 0o640


@POSIX_ONLY
def test_save_repairs_default_storage_and_preserves_existing_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit save repairs default modes without discarding existing profiles."""
    config_path = tmp_path / ".sccfm-cli" / "config.json"
    config_path.parent.mkdir()
    config_path.parent.chmod(0o755)
    existing = _write_config(config_path, profile="existing")
    config_path.chmod(0o644)
    _use_default_path(monkeypatch, config_path)

    added = Profile(profile="added", region="eu", api_token="example-token-2")
    service = ProfileService()
    service.save(added)

    assert _mode(config_path.parent) == 0o700
    assert _mode(config_path) == 0o600
    assert service.load(existing.profile) == existing
    assert service.load(added.profile) == added


def test_non_posix_fallback_preserves_save_and_load_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Platforms without POSIX permissions should still persist configuration."""
    config_path = tmp_path / "config.json"
    expected = Profile(profile="default", region="us", api_token="example-token")
    monkeypatch.setattr(
        ProfileService,
        "_supports_posix_permissions",
        staticmethod(lambda: False),
    )

    service = ProfileService(path=config_path)
    service.save(expected)

    assert service.load(expected.profile) == expected

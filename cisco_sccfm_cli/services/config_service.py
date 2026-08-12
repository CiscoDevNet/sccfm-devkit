# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import stat
from errno import ELOOP, ENOTDIR
from pathlib import Path
from typing import Any, Mapping, TextIO, cast

from cisco_sccfm_cli.models import Config

_CONFIG_DIR = Path.home() / ".sccfm-cli"
_CONFIG_FILE = _CONFIG_DIR / "config.json"
_CONFIG_DIR_MODE = 0o700
_CONFIG_FILE_MODE = 0o600


class ConfigService:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _CONFIG_FILE
        self._uses_default_path = self._path == _CONFIG_FILE

    def load(self, profile: str) -> Config | None:
        profiles = self._load_profiles()
        profile_data = profiles.get(profile)
        if not profile_data:
            return None
        return Config(
            profile=profile,
            region=profile_data["region"],
            api_token=profile_data["api_token"],
        )

    def save(self, config: Config) -> None:
        self._validate_storage_path()
        self._ensure_parent_directory()
        self._validate_storage_path()
        handle, created = self._open_directly_for_update()
        with handle:
            profiles = {} if created else self._read_profiles_for_update(handle)
            profiles[config.profile] = {
                "region": config.region,
                "api_token": config.api_token,
            }
            self._rewrite(handle, {"profiles": profiles})

    def list_profiles(self) -> list[Config]:
        profiles = self._load_profiles()
        return [
            Config(profile=name, region=data["region"], api_token=data["api_token"])
            for name, data in sorted(profiles.items())
        ]

    def _load_profiles(self) -> dict[str, dict[str, Any]]:
        self._validate_storage_path()
        self._validate_read_permissions()
        self._prepare_default_directory_permissions(repair=False)
        try:
            handle = self._open_directly_for_read()
        except FileNotFoundError:
            return {}
        with handle:
            data = json.load(handle)
        return dict(data.get("profiles", {}))

    def _read_profiles_for_update(self, handle: TextIO) -> dict[str, dict[str, Any]]:
        data = json.load(handle)
        return dict(data.get("profiles", {}))

    def _rewrite(self, handle: TextIO, payload: Mapping[str, Any]) -> None:
        descriptor = handle.fileno()
        self._ensure_regular_descriptor(descriptor)
        handle.seek(0)
        os.ftruncate(descriptor, 0)
        json.dump(payload, handle, indent=2)

    def _ensure_parent_directory(self) -> None:
        self._validate_parent_directory()
        created = False
        try:
            self._path.parent.mkdir(parents=True, mode=_CONFIG_DIR_MODE)
            created = True
        except FileExistsError:
            if not self._path.parent.is_dir():
                raise

        self._validate_parent_directory()
        if not self._supports_posix_permissions():
            return
        if self._uses_default_path:
            self._prepare_default_directory_permissions(repair=True)
        elif created:
            self._harden_parent_directory()

    def _prepare_default_directory_permissions(self, *, repair: bool) -> None:
        if not self._supports_posix_permissions() or not self._uses_default_path:
            return
        try:
            descriptor = self._open_validated_parent_directory()
        except FileNotFoundError:
            return
        try:
            if repair:
                os.fchmod(descriptor, _CONFIG_DIR_MODE)
            else:
                self._require_descriptor_mode(
                    descriptor,
                    expected=_CONFIG_DIR_MODE,
                    label="default configuration directory",
                )
        finally:
            os.close(descriptor)

    def _validate_storage_path(self) -> None:
        """Reject path types that must never be opened or permission-hardened."""
        self._validate_parent_directory()
        self._validate_configuration_file()

    def _validate_parent_directory(self) -> None:
        for parent in (self._path.parent, *self._path.parent.parents):
            try:
                mode = parent.lstat().st_mode
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(mode):
                raise ValueError(
                    f"Configuration directory path must not contain symbolic links: {parent}"
                )

        try:
            mode = self._path.parent.lstat().st_mode
        except FileNotFoundError:
            return
        if not stat.S_ISDIR(mode):
            raise ValueError(f"Configuration parent must be a directory: {self._path.parent}")

    def _validate_configuration_file(self) -> None:
        try:
            mode = self._path.lstat().st_mode
        except FileNotFoundError:
            return
        if stat.S_ISLNK(mode):
            raise ValueError(f"Configuration file must not be a symbolic link: {self._path}")
        if not stat.S_ISREG(mode):
            raise ValueError(f"Configuration path must be a regular file: {self._path}")

    def _validate_read_permissions(self) -> None:
        """Fail closed before opening storage whose mode may prevent a useful error."""
        if not self._supports_posix_permissions():
            return
        if self._uses_default_path:
            self._require_path_mode_if_present(
                self._path.parent,
                expected=_CONFIG_DIR_MODE,
                label="default configuration directory",
            )
        self._require_path_mode_if_present(
            self._path,
            expected=_CONFIG_FILE_MODE,
            label="configuration file",
        )

    def _require_path_mode_if_present(self, path: Path, *, expected: int, label: str) -> None:
        try:
            actual = stat.S_IMODE(path.lstat().st_mode)
        except FileNotFoundError:
            return
        self._require_mode(actual=actual, expected=expected, label=label)

    def _open_directly_for_read(self) -> TextIO:
        descriptor = self._open_read_descriptor()
        try:
            if self._supports_posix_permissions():
                self._require_descriptor_mode(
                    descriptor,
                    expected=_CONFIG_FILE_MODE,
                    label="configuration file",
                )
            return cast(TextIO, os.fdopen(descriptor, "r", encoding="utf-8"))
        except BaseException:
            os.close(descriptor)
            raise

    def _open_directly_for_update(self) -> tuple[TextIO, bool]:
        descriptor, created = self._open_update_descriptor()
        try:
            if self._supports_posix_permissions():
                os.fchmod(descriptor, _CONFIG_FILE_MODE)
            handle = cast(TextIO, os.fdopen(descriptor, "r+", encoding="utf-8"))
            return handle, created
        except BaseException:
            os.close(descriptor)
            raise

    def _open_read_descriptor(self) -> int:
        flags = os.O_RDONLY | self._safe_open_flags()
        if not self._supports_posix_permissions():
            descriptor = os.open(self._path, flags)
            try:
                self._ensure_regular_descriptor(descriptor)
                return descriptor
            except BaseException:
                os.close(descriptor)
                raise

        parent_descriptor = self._open_validated_parent_directory()
        try:
            return self._open_relative_descriptor(parent_descriptor, flags=flags)
        finally:
            os.close(parent_descriptor)

    def _open_update_descriptor(self) -> tuple[int, bool]:
        flags = os.O_RDWR | self._safe_open_flags()
        if not self._supports_posix_permissions():
            return self._open_update_descriptor_without_dir_fd(flags)

        parent_descriptor = self._open_validated_parent_directory()
        try:
            try:
                descriptor = self._open_relative_descriptor(
                    parent_descriptor,
                    flags=flags,
                )
                return descriptor, False
            except FileNotFoundError:
                descriptor = self._open_relative_descriptor(
                    parent_descriptor,
                    flags=flags | os.O_CREAT | os.O_EXCL,
                    mode=_CONFIG_FILE_MODE,
                )
                return descriptor, True
        finally:
            os.close(parent_descriptor)

    def _open_update_descriptor_without_dir_fd(self, flags: int) -> tuple[int, bool]:
        try:
            descriptor = os.open(self._path, flags)
        except FileNotFoundError:
            descriptor = os.open(
                self._path,
                flags | os.O_CREAT | os.O_EXCL,
                _CONFIG_FILE_MODE,
            )
            created = True
        else:
            created = False
        try:
            self._ensure_regular_descriptor(descriptor)
            return descriptor, created
        except BaseException:
            os.close(descriptor)
            raise

    def _open_relative_descriptor(
        self,
        parent_descriptor: int,
        *,
        flags: int,
        mode: int = 0o777,
    ) -> int:
        descriptor = os.open(
            self._path.name,
            flags,
            mode,
            dir_fd=parent_descriptor,
        )
        try:
            self._ensure_regular_descriptor(
                descriptor,
                parent_descriptor=parent_descriptor,
            )
            self._ensure_parent_descriptor_matches_path(parent_descriptor)
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def _ensure_regular_descriptor(
        self,
        descriptor: int,
        *,
        parent_descriptor: int | None = None,
    ) -> None:
        descriptor_stat = os.fstat(descriptor)
        if not stat.S_ISREG(descriptor_stat.st_mode):
            raise ValueError(f"Configuration path must be a regular file: {self._path}")
        try:
            path_stat = self._configuration_path_stat(parent_descriptor)
        except FileNotFoundError as exc:
            raise ValueError(
                f"Configuration path changed while being opened: {self._path}"
            ) from exc
        if stat.S_ISLNK(path_stat.st_mode) or not os.path.samestat(descriptor_stat, path_stat):
            raise ValueError(f"Configuration path changed while being opened: {self._path}")

    def _configuration_path_stat(self, parent_descriptor: int | None) -> os.stat_result:
        if parent_descriptor is None:
            return self._path.lstat()
        return os.stat(
            self._path.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )

    def _harden_parent_directory(self) -> None:
        descriptor = self._open_validated_parent_directory()
        try:
            os.fchmod(descriptor, _CONFIG_DIR_MODE)
        finally:
            os.close(descriptor)

    def _open_validated_parent_directory(self) -> int:
        parent = self._path.parent.absolute()
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | self._safe_open_flags()
        descriptor = os.open(parent.anchor, flags)
        try:
            for component in parent.parts[1:]:
                child_descriptor = self._open_child_directory(descriptor, component, flags)
                os.close(descriptor)
                descriptor = child_descriptor
            self._ensure_parent_descriptor_matches_path(descriptor)
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def _open_child_directory(self, parent_descriptor: int, name: str, flags: int) -> int:
        try:
            descriptor = os.open(name, flags, dir_fd=parent_descriptor)
        except OSError as exc:
            if exc.errno in (ELOOP, ENOTDIR):
                raise self._directory_changed_error() from exc
            raise
        try:
            descriptor_stat = os.fstat(descriptor)
            path_stat = os.stat(
                name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISDIR(descriptor_stat.st_mode)
                or stat.S_ISLNK(path_stat.st_mode)
                or not os.path.samestat(descriptor_stat, path_stat)
            ):
                raise self._directory_changed_error()
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def _ensure_parent_descriptor_matches_path(self, descriptor: int) -> None:
        descriptor_stat = os.fstat(descriptor)
        try:
            path_stat = self._path.parent.lstat()
        except FileNotFoundError as exc:
            raise self._directory_changed_error() from exc
        if stat.S_ISLNK(path_stat.st_mode) or not os.path.samestat(descriptor_stat, path_stat):
            raise self._directory_changed_error()

    def _directory_changed_error(self) -> ValueError:
        return ValueError(
            f"Configuration directory changed or contains a symbolic link: {self._path.parent}"
        )

    @staticmethod
    def _require_descriptor_mode(descriptor: int, *, expected: int, label: str) -> None:
        actual = stat.S_IMODE(os.fstat(descriptor).st_mode)
        ConfigService._require_mode(actual=actual, expected=expected, label=label)

    @staticmethod
    def _require_mode(*, actual: int, expected: int, label: str) -> None:
        if actual == expected:
            return
        raise PermissionError(
            f"Unsafe {label} permissions: expected {expected:04o}, found {actual:04o}. "
            "Fix the mode with chmod or rerun 'sccfm-cli configure' with the profile settings "
            "to repair it."
        )

    @staticmethod
    def _safe_open_flags() -> int:
        return getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)

    @staticmethod
    def _supports_posix_permissions() -> bool:
        return os.name == "posix"

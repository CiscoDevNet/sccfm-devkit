# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Runtime schema export for the Click command tree."""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, cast

import click
from scc_firewall_manager_sdk import ConfigState, ConnectivityState, EntityType

SCHEMA_VERSION = "1.0"
_DISTRIBUTION_NAME = "cisco-sccfm-devkit"

_SCCFM_FREE_COMMANDS = {
    ("configure",),
    ("schema",),
    ("schema", "export"),
}

_LOCAL_SIDE_EFFECT_COMMANDS: dict[tuple[str, ...], str] = {
    ("configure",): "Writes the selected profile to the local sccfm-cli configuration file.",
}

_SCCFM_READONLY_LEAF_NAMES = {
    "compatible-versions",
    "get",
    "ha-check",
    "list",
    "list-boot-registry",
    "list-files",
    "list-local-users",
    "list-not-on-version",
    "show",
    "status",
    "transaction",
}

_READ_ONLY_SPECIAL_PATHS = {
    ("inventory", "devices", "cdfmc-managed-ftd", "cli", "execute"),
}

_MUTATING_SPECIAL_PATHS = {
    ("inventory", "devices", "asa", "cli", "execute"),
}

_OPTIONAL_DEVICE_SELECTOR_PATHS = {
    ("inventory", "devices", "asa", "list-not-on-version"),
    ("inventory", "devices", "ftd", "list-not-on-version"),
}

_NO_AUTH_NOTES = "No stored SCCFM profile is required."
_PROFILE_AUTH_NOTES = "Requires a configured sccfm-cli profile containing region and API token."

_DEVICE_QUERYABLE_FIELDS = [
    {
        "name": "name",
        "type": "string",
        "description": "Device name. Wildcards are accepted by the SCCFM Lucene query API.",
        "examples": ["name:branch-*"],
        "natural_language_aliases": ["named", "name", "called"],
    },
    {
        "name": "uid",
        "type": "string",
        "description": "Device UID.",
        "examples": ["uid:<device-uid>"],
        "natural_language_aliases": ["uid", "id"],
    },
    {
        "name": "deviceType",
        "type": "choice",
        "description": "SCCFM device type.",
        "values": [member.value for member in EntityType],
        "examples": ["deviceType:ASA"],
        "natural_language_aliases": ["type", "device type", "asa", "ftd"],
    },
    {
        "name": "connectivityState",
        "type": "choice",
        "description": "Device connectivity state. Use ONLINE for online devices.",
        "values": [member.value for member in ConnectivityState],
        "examples": ["connectivityState:ONLINE"],
        "natural_language_aliases": ["online", "offline", "reachable", "unreachable"],
    },
    {
        "name": "configState",
        "type": "choice",
        "description": "Device configuration sync state.",
        "values": [member.value for member in ConfigState],
        "examples": ["configState:SYNCED"],
        "natural_language_aliases": ["synced", "not synced", "configuration state"],
    },
]

_OBJECT_QUERYABLE_FIELDS = [
    {
        "name": "name",
        "type": "string",
        "description": "Object name. Wildcards are accepted by the SCCFM Lucene query API.",
        "examples": ["name:web-*"],
        "natural_language_aliases": ["named", "name", "called"],
    },
    {
        "name": "content",
        "type": "string",
        "description": "Object content value, such as an IP address, CIDR, FQDN, or URL.",
        "examples": ["content:10.0.0.0/24"],
        "natural_language_aliases": ["contains", "content", "value"],
    },
]


def build_cli_schema(root: click.Command, *, prog_name: str = "sccfm-cli") -> dict[str, Any]:
    """Return a JSON-serializable schema for the full Click command tree."""
    root_options = [
        _option_schema(param, scope="global")
        for param in root.params
        if isinstance(param, click.Option)
    ]
    command_tree = [
        _command_schema(path=path, command=command, prog_name=prog_name)
        for path, command in _walk_commands(root)
    ]
    commands = [command for command in command_tree if command["kind"] == "command"]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool_name": prog_name,
        "application": prog_name,
        "version": _package_version(),
        "generated_at": datetime.now(UTC).isoformat(),
        "description": _first_line(root.help),
        "global_options": root_options,
        "commands": commands,
        "command_tree": command_tree,
    }


def _walk_commands(
    command: click.Command, path: tuple[str, ...] = ()
) -> list[tuple[tuple[str, ...], click.Command]]:
    paths: list[tuple[tuple[str, ...], click.Command]] = []
    if path:
        paths.append((path, command))
    if isinstance(command, click.Group):
        for name, child in sorted(command.commands.items()):
            paths.extend(_walk_commands(child, (*path, name)))
    return paths


def _command_schema(
    *,
    path: tuple[str, ...],
    command: click.Command,
    prog_name: str,
) -> dict[str, Any]:
    is_group = isinstance(command, click.Group)
    options = [
        _option_schema(param, scope="command")
        for param in command.params
        if isinstance(param, click.Option)
    ]
    option_names = {option["name"] for option in options}
    mutates_sccfm = _mutates_sccfm(path=path, is_group=is_group)
    side_effects = _side_effects(path=path, mutates_sccfm=mutates_sccfm)
    constraints = _constraints(path=path, option_names=option_names, mutates_sccfm=mutates_sccfm)
    command_name = " ".join(path)
    return {
        "path": list(path),
        "command": _command_text(path, prog_name=prog_name),
        "name": command_name,
        "command_name": path[-1],
        "kind": "group" if is_group else "command",
        "description": _first_line(command.help),
        "readonly": not mutates_sccfm,
        "side_effects": side_effects,
        "auth": _auth(path=path, is_group=is_group),
        "bulk_file_format": None,
        "queryable_fields": _queryable_fields(path=path, option_names=option_names),
        "field_notes": _field_notes(path=path, option_names=option_names),
        "options": options,
        "option_groups": _option_constraint_groups(constraints),
        "constraints": constraints,
        "examples": _examples(path=path, command=command, prog_name=prog_name),
        "subcommands": sorted(command.commands) if isinstance(command, click.Group) else [],
    }


def _queryable_fields(
    *,
    path: tuple[str, ...],
    option_names: set[str],
) -> list[dict[str, Any]] | None:
    if "query" not in option_names:
        return None
    if _is_device_query_path(path):
        return _DEVICE_QUERYABLE_FIELDS
    if _is_object_query_path(path):
        return _OBJECT_QUERYABLE_FIELDS
    return None


def _field_notes(
    *,
    path: tuple[str, ...],
    option_names: set[str],
) -> list[str] | None:
    if "query" not in option_names:
        return None
    if _is_typed_device_query_path(path):
        return [
            (
                "This command automatically adds its deviceType filter. Do not add a "
                "deviceType clause unless the user explicitly asks for a different filter."
            ),
            "Translate 'online' to connectivityState:ONLINE.",
        ]
    if _is_device_query_path(path):
        return [
            "Use Lucene syntax for --query.",
            "Translate 'online' to connectivityState:ONLINE.",
        ]
    if _is_object_query_path(path):
        return ["Use Lucene syntax for --query."]
    return None


def _is_device_query_path(path: tuple[str, ...]) -> bool:
    return len(path) >= 3 and path[:2] == ("inventory", "devices")


def _is_typed_device_query_path(path: tuple[str, ...]) -> bool:
    return len(path) >= 4 and path[:2] == ("inventory", "devices")


def _is_object_query_path(path: tuple[str, ...]) -> bool:
    return len(path) >= 3 and path[0] == "objects"


def _package_version() -> str:
    try:
        return version(_DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return _pyproject_version() or "unknown"


def _pyproject_version() -> str | None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None

    tool = pyproject.get("tool")
    if not isinstance(tool, dict):
        return None

    poetry = tool.get("poetry")
    if not isinstance(poetry, dict):
        return None

    project_version = poetry.get("version")
    if not isinstance(project_version, str) or not project_version:
        return None

    return project_version


def _command_text(path: Sequence[str], *, prog_name: str) -> str:
    if not path:
        return prog_name
    return f"{prog_name} {' '.join(path)}"


def _first_line(text: str | None) -> str:
    if not text:
        return ""
    return text.strip().splitlines()[0].rstrip(".")


def _mutates_sccfm(*, path: tuple[str, ...], is_group: bool) -> bool:
    if is_group:
        return False
    if path in _SCCFM_FREE_COMMANDS:
        return False
    if path in _READ_ONLY_SPECIAL_PATHS:
        return False
    if path in _MUTATING_SPECIAL_PATHS:
        return True
    return path[-1] not in _SCCFM_READONLY_LEAF_NAMES


def _side_effects(*, path: tuple[str, ...], mutates_sccfm: bool) -> list[str]:
    effects: list[str] = []
    if mutates_sccfm:
        effects.append("May change state in SCC Firewall Manager or on managed devices.")
    if path in _LOCAL_SIDE_EFFECT_COMMANDS:
        effects.append(_LOCAL_SIDE_EFFECT_COMMANDS[path])
    return effects


def _auth(*, path: tuple[str, ...], is_group: bool) -> dict[str, Any]:
    requirements = _auth_requirements(path=path, is_group=is_group)
    return {
        "mode": "sccfm_profile" if requirements["requires_profile"] else "none",
        "requires_profile": requirements["requires_profile"],
        "requires_api_token": requirements["requires_api_token"],
        "profile_option": "--profile" if requirements["requires_profile"] else None,
        "config_path_option": "--config-path" if requirements["requires_profile"] else None,
        "notes": requirements["notes"],
    }


def _auth_requirements(*, path: tuple[str, ...], is_group: bool) -> dict[str, Any]:
    if is_group or path in _SCCFM_FREE_COMMANDS:
        return {
            "requires_profile": False,
            "requires_api_token": False,
            "notes": _NO_AUTH_NOTES,
        }
    return {
        "requires_profile": True,
        "requires_api_token": True,
        "notes": _PROFILE_AUTH_NOTES,
    }


def _option_schema(option: click.Option, *, scope: str) -> dict[str, Any]:
    option_type = _option_type(option)
    choices, value_constraints = _type_metadata(option.type)
    default, has_default = _default_value(option)
    return {
        "name": option.name or "",
        "flag": _preferred_flag(option),
        "scope": scope,
        "placement": "before_command_path" if scope == "global" else "after_command_path",
        "aliases": [*option.opts, *option.secondary_opts],
        "type": option_type,
        "required": bool(option.required),
        "description": _first_line(option.help),
        "values": choices,
        "value_constraints": value_constraints,
        "default": default,
        "has_default": has_default,
        "multiple": bool(option.multiple),
        "nargs": option.nargs,
        "is_flag": bool(option.is_flag),
        "is_bool_flag": bool(getattr(option, "is_bool_flag", False)),
        "sensitive": bool(option.hide_input),
        "envvar": _envvar(option.envvar),
        "metavar": option.metavar,
    }


def _preferred_flag(option: click.Option) -> str:
    long_opts = [opt for opt in option.opts if opt.startswith("--")]
    if long_opts:
        return str(long_opts[0])
    return str(option.opts[0]) if option.opts else (option.name or "")


def _option_type(option: click.Option) -> str:
    if option.is_flag:
        return "boolean"
    parameter_type = option.type
    if isinstance(parameter_type, click.Choice):
        return "choice"
    if isinstance(parameter_type, click.Path):
        return "path"
    if isinstance(parameter_type, click.IntRange | click.types.IntParamType):
        return "integer"
    if isinstance(parameter_type, click.FloatRange | click.types.FloatParamType):
        return "float"
    if isinstance(parameter_type, click.types.BoolParamType):
        return "boolean"
    return "string"


def _type_metadata(
    parameter_type: click.ParamType[Any],
) -> tuple[list[str] | None, dict[str, Any] | None]:
    if isinstance(parameter_type, click.Choice):
        return list(parameter_type.choices), {"case_sensitive": parameter_type.case_sensitive}
    if isinstance(parameter_type, click.IntRange | click.FloatRange):
        return None, {
            "min": parameter_type.min,
            "max": parameter_type.max,
            "min_open": parameter_type.min_open,
            "max_open": parameter_type.max_open,
            "clamp": parameter_type.clamp,
        }
    return None, None


def _default_value(option: click.Option) -> tuple[Any, bool]:
    default = option.default
    if _is_unset(default):
        return None, False
    if callable(default):
        return _callable_name(default), True
    return default, True


def _is_unset(value: object) -> bool:
    return value.__class__.__name__ == "Sentinel" and getattr(value, "name", None) == "UNSET"


def _callable_name(value: object) -> str:
    return getattr(value, "__name__", value.__class__.__name__)


def _envvar(envvar: str | Sequence[str] | None) -> str | list[str] | None:
    if envvar is None or isinstance(envvar, str):
        return envvar
    return list(envvar)


def _option_constraint_groups(constraints: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for constraint in constraints:
        if constraint["type"] == "mutually_exclusive":
            options = cast(list[str], constraint["options"])
            groups.append(
                {
                    "name": "_or_".join(options),
                    "mutually_exclusive": True,
                    "required": cast(int, constraint.get("min_required", 0)) > 0,
                    "description": constraint["description"],
                    "options": options,
                }
            )
        elif constraint["type"] == "exactly_one_unless":
            options = cast(list[str], constraint["options"])
            groups.append(
                {
                    "name": "_or_".join(options),
                    "mutually_exclusive": True,
                    "required": False,
                    "description": constraint["description"],
                    "options": options,
                }
            )
        elif constraint["type"] == "depends_on":
            option = cast(str, constraint["option"])
            groups.append(
                {
                    "name": f"{option}_requires_{constraint['requires']}",
                    "dependent": True,
                    "requires": constraint["requires"],
                    "description": constraint["description"],
                    "options": [option],
                }
            )
        elif constraint["type"] == "requires_any":
            options = cast(list[str], constraint["options"])
            groups.append(
                {
                    "name": "_or_".join(options),
                    "requires_any": True,
                    "required": True,
                    "description": constraint["description"],
                    "options": options,
                }
            )
    return groups


def _constraints(
    *,
    path: tuple[str, ...],
    option_names: set[str],
    mutates_sccfm: bool,
) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    constraints.extend(_device_selector_constraints(path=path, option_names=option_names))
    constraints.extend(_object_identifier_constraints(option_names=option_names))
    constraints.extend(_path_specific_constraints(path=path, option_names=option_names))
    if mutates_sccfm and "check" in option_names:
        constraints.append(
            {
                "type": "mode",
                "option": "check",
                "effect": "Preflight only; do not perform the SCCFM-changing operation.",
            }
        )
    return constraints


def _device_selector_constraints(
    *,
    path: tuple[str, ...],
    option_names: set[str],
) -> list[dict[str, Any]]:
    if {"device_name", "device_uid", "query"}.issubset(option_names):
        return [
            {
                "type": "requires_any",
                "options": ["device_name", "device_uid", "query"],
                "description": "Provide at least one device selector.",
            },
            {
                "type": "incompatible",
                "options": ["query", "device_name", "device_uid"],
                "description": "--query cannot be combined with --device-name or --device-uid.",
            },
        ]

    selector_names = _present(option_names, ("device_name", "query", "device_uids"))
    if len(selector_names) < 2:
        selector_names = _present(option_names, ("query", "device_uids"))
    if len(selector_names) < 2:
        return []

    min_required = 0 if path in _OPTIONAL_DEVICE_SELECTOR_PATHS else 1
    description = "Provide only one device selector."
    if min_required == 1:
        description = "Provide exactly one device selector."
    return [
        {
            "type": "mutually_exclusive",
            "options": selector_names,
            "min_required": min_required,
            "max_allowed": 1,
            "description": description,
        }
    ]


def _object_identifier_constraints(option_names: set[str]) -> list[dict[str, Any]]:
    if {"uid", "name"}.issubset(option_names):
        return [
            {
                "type": "mutually_exclusive",
                "options": ["uid", "name"],
                "min_required": 1,
                "max_allowed": 1,
                "description": "Identify the object by UID or by name, not both.",
            }
        ]
    return []


def _path_specific_constraints(
    *,
    path: tuple[str, ...],
    option_names: set[str],
) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    if path == ("inventory", "devices", "asa", "cli", "execute"):
        constraints.append(_exactly_one_unless("script", "script_file", unless="check"))
    if path == ("inventory", "devices", "cdfmc-managed-ftd", "cli", "execute"):
        constraints.append(_required_unless("command", unless="check"))
        constraints.append(
            {
                "type": "value_prefix",
                "option": "command",
                "prefix": "show",
                "case_sensitive": False,
                "description": "--command must be 'show' or start with 'show '.",
            }
        )
    if path == ("inventory", "devices", "asa", "onboard"):
        constraints.append(
            _required_unless("device_address", "username", "connector_type", unless="check")
        )
        constraints.append(
            {
                "type": "required_when",
                "option": "connector_name",
                "when": {"option": "connector_type", "equals": "SDC"},
                "description": "--connector-name is required when --connector-type is SDC.",
            }
        )
    if path == ("inventory", "devices", "cdfmc-managed-ftd", "onboard"):
        constraints.append(
            {
                "type": "depends_on",
                "option": "virtual",
                "requires": "performance_tier",
                "description": "--virtual requires --performance-tier.",
            }
        )
    if path == ("inventory", "devices", "ftd", "list-not-on-version"):
        constraints.append(
            {
                "type": "mutually_exclusive",
                "options": ["version", "recommended"],
                "min_required": 1,
                "max_allowed": 1,
                "description": "Provide either --version or --recommended.",
            }
        )
    if path == ("inventory", "devices", "asa", "upgrade", "trigger"):
        constraints.append(
            {
                "type": "requires_any",
                "options": ["software_version", "asdm_version"],
                "description": "Provide at least one target version.",
            }
        )
    if path == ("inventory", "devices", "asa", "shun", "add"):
        constraints.extend(
            [
                _depends_on("source_port", "dest_ip"),
                _depends_on("dest_port", "dest_ip"),
                _depends_on("protocol", "dest_ip"),
                {
                    "type": "input_shape",
                    "description": (
                        "--dest-ip, --source-port, --dest-port, and --protocol are only valid "
                        "with a single --source-ip value that does not include an inline tuple."
                    ),
                    "options": ["source_ip", "dest_ip", "source_port", "dest_port", "protocol"],
                },
            ]
        )
    if path == ("inventory", "devices", "asa", "smartlicense"):
        constraints.extend(
            [
                _required_unless("feature_tier", unless="check"),
                {
                    "type": "mutually_exclusive",
                    "options": ["token", "token_file"],
                    "min_required": 0,
                    "max_allowed": 1,
                    "description": (
                        "Use at most one explicit Smart Licensing token source; omit both "
                        "for the hidden interactive prompt."
                    ),
                },
            ]
        )
    if path == ("objects", "network", "create") and "value" in option_names:
        constraints.append(_required_unless("value", unless="check"))
    if path == ("objects", "network-group", "create"):
        constraints.append(
            {
                "type": "requires_any",
                "options": ["referenced_object", "network_literal", "url_literal"],
                "description": "Provide at least one member or literal.",
            }
        )
    if path[-1:] in {("add-member",), ("remove-member",)} and "referenced_object" in option_names:
        constraints.append(
            {
                "type": "requires_any",
                "options": ["referenced_object"],
                "description": "Provide at least one referenced object.",
            }
        )
    if path in _UID_REQUIRED_PATHS and "uid" in option_names:
        constraints.append(
            {
                "type": "requires_any",
                "options": ["uid"],
                "description": "--uid is required.",
            }
        )
    if path == ("objects", "network", "update"):
        constraints.append(
            _requires_update_field("new_name", "value", "description", "labels", "tags")
        )
    if path == ("objects", "network-group", "update"):
        constraints.append(
            _requires_update_field("new_name", "referenced_object", "description", "labels", "tags")
        )
    if path == ("policies", "access-rule", "update"):
        constraints.append(
            _requires_update_field(
                "index",
                "rule_action",
                "remark",
                "source_network",
                "destination_network",
                "protocol",
                "source_port",
                "destination_port",
                "log_level",
                "log_interval",
                "active",
            )
        )
    return constraints


_UID_REQUIRED_PATHS = {
    ("objects", "add-override"),
    ("objects", "apply-override-as-default"),
    ("objects", "delete-override"),
    ("objects", "edit-override"),
    ("objects", "show"),
    ("objects", "update-default"),
}


def _required_unless(*options: str, unless: str) -> dict[str, Any]:
    return {
        "type": "required_unless",
        "options": list(options),
        "unless": unless,
        "description": f"Required unless --{unless.replace('_', '-')} is set.",
    }


def _exactly_one_unless(*options: str, unless: str) -> dict[str, Any]:
    option_flags = ", ".join(f"--{option.replace('_', '-')}" for option in options)
    return {
        "type": "exactly_one_unless",
        "options": list(options),
        "unless": unless,
        "description": (
            f"Provide exactly one of {option_flags} unless --{unless.replace('_', '-')} is set."
        ),
    }


def _depends_on(option: str, requires: str) -> dict[str, Any]:
    return {
        "type": "depends_on",
        "option": option,
        "requires": requires,
        "description": (f"--{option.replace('_', '-')} requires --{requires.replace('_', '-')}."),
    }


def _requires_update_field(*options: str) -> dict[str, Any]:
    return {
        "type": "requires_any",
        "options": list(options),
        "description": "At least one update field must be provided.",
    }


def _present(option_names: set[str], names: Iterable[str]) -> list[str]:
    return [name for name in names if name in option_names]


def _examples(
    *,
    path: tuple[str, ...],
    command: click.Command,
    prog_name: str,
) -> list[str]:
    command_text = _command_text(path, prog_name=prog_name)
    examples = [f"{command_text} --help"]
    if isinstance(command, click.Group):
        return examples

    options = [param for param in command.params if isinstance(param, click.Option)]
    required_option_names = _required_option_names(options)
    constraints = _constraints(
        path=path,
        option_names={option.name or "" for option in options},
        mutates_sccfm=_mutates_sccfm(path=path, is_group=False),
    )
    example_option_names = _example_option_names(
        required_option_names=required_option_names,
        constraints=constraints,
    )
    parts = [command_text, *_example_option_parts(options, example_option_names)]
    if _has_option(command.params, "format") and "schema export" not in command_text:
        parts.extend(["--format", "json"])
    examples.append(" ".join(parts))
    return examples


def _required_option_names(options: Sequence[click.Option]) -> list[str]:
    return [
        option.name
        for option in options
        if option.required and option.name is not None and option.name != "config_path"
    ]


def _example_option_names(
    *,
    required_option_names: Sequence[str],
    constraints: Sequence[dict[str, Any]],
) -> list[str]:
    names = list(required_option_names)
    for constraint in constraints:
        constraint_type = constraint["type"]
        if constraint_type == "mutually_exclusive":
            min_required = cast(int, constraint.get("min_required", 0))
            if min_required > 0:
                _append_missing(
                    names, _preferred_example_name(cast(list[str], constraint["options"]))
                )
        elif constraint_type == "requires_any":
            _append_missing(
                names,
                _preferred_example_name(cast(list[str], constraint["options"])),
            )
        elif constraint_type == "required_unless":
            for option_name in cast(list[str], constraint["options"]):
                _append_missing(names, option_name)
        elif constraint_type == "exactly_one_unless":
            _append_missing(
                names,
                _preferred_example_name(cast(list[str], constraint["options"])),
            )
        elif constraint_type == "required_when":
            _append_missing(names, cast(str, constraint["option"]))
    return names


def _preferred_example_name(option_names: Sequence[str]) -> str:
    preferred_order = (
        "uid",
        "device_name",
        "query",
        "tenant_uid",
        "tenant",
        "name",
        "version",
    )
    for preferred in preferred_order:
        if preferred in option_names:
            return preferred
    return option_names[0]


def _append_missing(names: list[str], name: str) -> None:
    if name not in names:
        names.append(name)


def _example_option_parts(
    options: Sequence[click.Option],
    option_names: Sequence[str],
) -> list[str]:
    option_by_name = {option.name: option for option in options}
    parts: list[str] = []
    for option_name in option_names:
        option = option_by_name.get(option_name)
        if option is None or option.hide_input:
            continue
        flag = _preferred_flag(option)
        if option.is_flag:
            parts.append(flag)
        else:
            parts.extend([flag, _example_value(option)])
    return parts


def _example_value(option: click.Option) -> str:
    parameter_type = option.type
    if isinstance(parameter_type, click.Choice):
        choice = next(iter(parameter_type.choices), None)
        if choice is not None:
            return str(choice)
    return f"<{(option.name or 'value').replace('_', '-')}>"


def _has_option(params: Sequence[click.Parameter], name: str) -> bool:
    return any(isinstance(param, click.Option) and param.name == name for param in params)

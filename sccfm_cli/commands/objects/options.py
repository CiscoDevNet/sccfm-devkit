from __future__ import annotations

from pathlib import Path
from typing import List

import click


def name_option() -> click.Option:
    """Required --name option for object name."""
    return click.Option(
        ["-n", "--name"],
        required=True,
        type=str,
        help="The name of the object.",
    )


def value_option() -> click.Option:
    """Required --value option for network object content."""
    return click.Option(
        ["-v", "--value"],
        required=True,
        type=str,
        help="The literal value (IP address, CIDR, or range).",
    )


def description_option() -> click.Option:
    """Optional --description option."""
    return click.Option(
        ["-d", "--description"],
        default=None,
        type=str,
        help="A human-readable description of the object.",
    )


def labels_option() -> click.Option:
    """Optional --labels option for object labels."""
    return click.Option(
        ["-l", "--labels"],
        default=None,
        multiple=True,
        type=str,
        help="Labels to attach to the object (can be specified multiple times).",
    )


def tags_option() -> click.Option:
    """Optional --tags option for object tags.

    Formats:
      - key=value or key=val1,val2  (stored as tags)
      - standalone or val1,val2     (stored under the "labels" key)

    Examples:
      --tags env=prod,staging --tags production
    """
    return click.Option(
        ["-t", "--tags"],
        default=None,
        multiple=True,
        type=str,
        help="Tags in key=value format (value can be comma-separated; repeatable).",
    )


def format_option() -> click.Option:
    """Reusable --format option for output formatting."""
    return click.Option(
        ["--format"],
        type=click.Choice(["table", "json"], case_sensitive=False),
        default="table",
        show_default=True,
        help="Output format.",
    )


def config_path_option() -> click.Option:
    """Reusable --config-path option."""
    return click.Option(
        ["--config-path"],
        type=click.Path(path_type=Path, resolve_path=True),
        default=None,
        envvar="SCCFM_CONFIG",
        show_default=False,
        help="Path to the configuration file (defaults to ~/.sccfm-cli/config.json).",
    )


def uid_option() -> click.Option:
    """Optional --uid option for object unique identifier."""
    return click.Option(
        ["-u", "--uid"],
        required=False,
        type=str,
        help="The unique identifier (UID) of the object.",
    )


def object_name_option() -> click.Option:
    """Optional --name option for object identification.

    This is distinct from name_option() which is required for creation.
    Used in operations where either UID or name can identify an object.
    """
    return click.Option(
        ["-n", "--name"],
        required=False,
        type=str,
        help="The name of the object (alternative to UID).",
    )


def object_create_params() -> List[click.Parameter]:
    """Complete set of options for network object create command."""
    return [
        name_option(),
        value_option(),
        description_option(),
        labels_option(),
        tags_option(),
        format_option(),
        config_path_option(),
    ]


def parse_tags(tags_tuple: tuple[str, ...] | None) -> dict[str, list[str]] | None:
    """Parse tag strings into a dictionary.

    Supported formats:
      - "key=val1,val2" — key with one or more comma-separated values
      - "val" or "val1,val2" — standalone values stored under the "labels" key

    Args:
        tags_tuple: Tuple of tag strings from the CLI.

    Returns:
        Dictionary mapping tag keys to lists of values, or None if no tags.
    """
    if not tags_tuple:
        return None

    result: dict[str, list[str]] = {}
    for tag_str in tags_tuple:
        if "=" not in tag_str:
            # Standalone tag(s): comma-separated values go under "labels"
            for val in tag_str.split(","):
                val = val.strip()
                if not val:
                    continue
                result.setdefault("labels", []).append(val)
            continue
        key, value = tag_str.split("=", 1)
        key = key.strip()
        if not key:
            raise click.BadParameter("Tag key cannot be empty.")
        values = [v.strip() for v in value.split(",") if v.strip()]
        if not values:
            raise click.BadParameter(f"Tag '{key}' must include at least one value.")
        if key in result:
            result[key].extend(values)
        else:
            result[key] = values
    return result if result else None


def object_delete_params() -> List[click.Parameter]:
    """Complete set of options for network object delete command."""
    return [
        uid_option(),
        object_name_option(),
        config_path_option(),
    ]

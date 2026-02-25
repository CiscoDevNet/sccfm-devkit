from __future__ import annotations

from typing import Any, List

import click

from sccfm_cli.commands.shared_options import (
    config_path_option,
    format_option,
    limit_option,
    offset_option,
)


def name_option() -> click.Option:
    """Required --name option for object name."""
    return click.Option(
        ["-n", "--name"],
        required=True,
        type=str,
        help="The name of the object.",
    )


def value_option(*, required: bool = True) -> click.Option:
    """Reusable --value option for network object content.

    Args:
        required: Whether the option is mandatory (True for create, False for update).
    """
    return click.Option(
        ["-v", "--value"],
        required=required,
        default=None if not required else None,
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




def query_option(*, required: bool = False) -> click.Option:
    """Reusable --query option for Lucene filtering.

    Args:
        required: Whether the option is mandatory.
    """
    kwargs: dict[str, Any] = {
        "required": required,
        "show_default": False,
        "help": "Lucene query string. Searchable fields: name, content.",
    }
    if not required:
        kwargs["default"] = None
    return click.Option(["-q", "--query"], **kwargs)


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


def object_list_params() -> List[click.Parameter]:
    """Complete set of options for network object list commands."""
    return [
        limit_option(),
        offset_option(),
        query_option(),
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


def new_name_option() -> click.Option:
    """Optional --new-name option for renaming an object."""
    return click.Option(
        ["--new-name"],
        required=False,
        type=str,
        default=None,
        help="The new name for the object.",
    )


def referenced_object_option() -> click.Option:
    """Repeatable --referenced-object option for referencing existing objects by UID or name."""
    return click.Option(
        ["-r", "--referenced-object"],
        default=None,
        multiple=True,
        type=str,
        help="UID or name of an existing network object to include (repeatable).",
    )


def network_literal_option() -> click.Option:
    """Repeatable --network-literal option for inline network values."""
    return click.Option(
        ["--network-literal"],
        default=None,
        multiple=True,
        type=str,
        help="Inline network literal (IP, CIDR, or range; repeatable).",
    )


def url_literal_option() -> click.Option:
    """Repeatable --url-literal option for inline URL values."""
    return click.Option(
        ["--url-literal"],
        default=None,
        multiple=True,
        type=str,
        help="Inline URL literal (repeatable).",
    )


def object_update_params() -> List[click.Parameter]:
    """Complete set of options for network object update command."""
    return [
        uid_option(),
        object_name_option(),
        new_name_option(),
        value_option(required=False),
        description_option(),
        labels_option(),
        tags_option(),
        format_option(),
        config_path_option(),
    ]


def group_create_params() -> List[click.Parameter]:
    """Complete set of options for network group create command."""
    return [
        name_option(),
        referenced_object_option(),
        network_literal_option(),
        url_literal_option(),
        description_option(),
        labels_option(),
        tags_option(),
        format_option(),
        config_path_option(),
    ]


def group_update_params() -> List[click.Parameter]:
    """Complete set of options for network group update command."""
    return [
        uid_option(),
        object_name_option(),
        new_name_option(),
        referenced_object_option(),
        description_option(),
        labels_option(),
        tags_option(),
        format_option(),
        config_path_option(),
    ]


def format_tags(tags: dict[str, list[str]]) -> str:
    """Format tags dict as readable key=value lines."""
    return "\n".join(f"{key}={','.join(values)}" for key, values in tags.items())

"""JSON payload helpers shared across phase modules.

The CLI's ``--format json`` output isn't uniform across commands: some
return a top-level list, some a single dict, some a paginated envelope
(``{items: [...]}`` or ``{results: [...]}``).  Normalizing once here
keeps phase modules focused on their assertions.
"""

from __future__ import annotations

# Common envelope keys that wrap a list of result rows in CLI JSON output.
_LIST_ENVELOPE_KEYS: tuple[str, ...] = (
    "results",
    "items",
    "boot_registry",
    "files",
)


def normalize_rows(payload: object) -> list[dict[str, object]]:
    """Coerce a CLI JSON payload into a flat list of dict rows.

    Accepts:
      - a list of dicts (returned as-is, filtered to dicts)
      - a dict envelope with one of ``_LIST_ENVELOPE_KEYS`` -> the list
      - a dict whose values are per-device row lists -> flattened
      - a single-row dict -> wrapped in a one-element list
    Anything else returns ``[]``.
    """
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in _LIST_ENVELOPE_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        # Per-device dict: flatten the list values.
        flattened: list[dict[str, object]] = []
        any_list_values = False
        for value in payload.values():
            if isinstance(value, list):
                any_list_values = True
                flattened.extend(row for row in value if isinstance(row, dict))
        if any_list_values:
            return flattened
        # Single-row dict.
        return [payload]
    return []

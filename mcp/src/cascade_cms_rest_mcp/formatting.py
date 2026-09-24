"""Concise/detailed asset formatting and search-result shaping.

Reaches into `Asset._data` directly (a leading-underscore attribute) - Asset
has no public bulk-iteration API, and the library's own
`edit_log_identifier_from_asset()` (cmstypes.py) already does the same thing,
so this is precedented, not a hack.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from cascade_cms.cmstypes import Asset, IdentifierType, ListElements

from . import query, security
from .references import find_references

# "structuredData" is Cascade's documented REST field name for data-bound
# asset types, but is NOT yet confirmed against a real payload in this repo
# (no fixture references it) - unlike "pageConfigurations", which
# Asset.__init__ already parses. Confirm this key name against a real
# cascade_read_asset (format="detailed") response against a live server; if
# it turns out to be wrong, only that one hint's specificity is affected - it
# falls through to the generic detailed-mode hint below, which is still
# correct.
_EXPAND_HINT_BY_KEY: dict[str, str] = {
    "structuredData": "cascade_get_data_structure",
    "pageConfigurations": "cascade_get_page_config",
}
# Steers any other collapsed top-level field (any asset shape - metadata sets
# included, not just pages/content-type-bound assets) toward a narrowed
# cascade_query_asset read first, rather than straight at a full detailed dump.
_DEFAULT_EXPAND_HINT = (
    'cascade_query_asset(query="<key>") for a narrowed read, or '
    'cascade_read_asset(format="detailed") for everything'
)

# `limit` is how many matches or list items a tool returns to the agent.
DEFAULT_LIMIT = 50
MIN_LIMIT = 1
MAX_LIMIT = 200


def clamp_limit(limit: int | None) -> int:
    """None -> DEFAULT_LIMIT; anything else clamped to MIN..MAX."""
    if limit is None:
        return DEFAULT_LIMIT
    return max(MIN_LIMIT, min(MAX_LIMIT, limit))


_SCALAR_TYPES = (str, int, float, bool, type(None))


def _collapse_value(key: str, value: Any) -> Any:
    if isinstance(value, _SCALAR_TYPES):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (dict, list)):
        return {
            "_collapsed": True,
            "count": len(value),
            "expand_with": _EXPAND_HINT_BY_KEY.get(key, _DEFAULT_EXPAND_HINT),
        }
    # Raw JSON only ever produces the types above; stringify rather than
    # crash on anything unforeseen.
    return str(value)


def format_asset(
    asset: Asset, *, format: Literal["concise", "detailed"]
) -> dict[str, Any]:
    if format == "detailed":
        return dict(asset._data)
    collapsed = {key: _collapse_value(key, value) for key, value in asset._data.items()}
    references = find_references(asset._data)
    if references:
        collapsed["_references"] = references
    return collapsed


def _collapse_query_match(path: str, value: Any) -> Any:
    """Same scalar/uuid/dict/list shaping as _collapse_value, but the
    expand_with hint points at a refined cascade_query_asset call using this
    match's own resolved path, rather than the page-specific hint table -
    works for any asset shape, not just the two keys _EXPAND_HINT_BY_KEY knows
    about."""
    if isinstance(value, _SCALAR_TYPES):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (dict, list)):
        return {
            "_collapsed": True,
            "count": len(value),
            "expand_with": f'cascade_query_asset(query="{path}", format="detailed")',
        }
    return str(value)


def format_query_result(
    matches: list[query.Match],
    *,
    format: Literal["concise", "detailed"],
    limit: int | None = None,
) -> dict[str, Any]:
    truncated = matches[: clamp_limit(limit)]
    if format == "detailed":
        shaped = [{"path": m.path, "value": m.value} for m in truncated]
    else:
        shaped = [
            {"path": m.path, "value": _collapse_query_match(m.path, m.value)}
            for m in truncated
        ]
    return {
        "matches": shaped,
        "total_count": len(matches),
        "has_more": len(matches) > len(truncated),
    }


def name_from_path(path: str | None) -> str | None:
    """Derive a pseudo display-name from an asset's path - Cascade search
    results carry no name/title field of their own."""
    if not path:
        return None
    segment = path.rstrip("/").rsplit("/", 1)[-1]
    return segment or None


def describe_element(element: IdentifierType) -> dict[str, Any]:
    return {
        "id": element.get_id,
        "type": element.get_type,
        "site": element.get_sitename,
        "path": element.get_path,
        "name": name_from_path(element.get_path),
    }


def format_search_results(
    elements: ListElements, *, limit: int | None = None
) -> dict[str, Any]:
    """Cascade's search endpoint has no limit/page-size param
    (`SearchInformation` has no such field) and exposes no total-match-count
    either, so limiting and counting both happen client-side here:
      - results whose type is blocked or not on the allowlist are
        dropped first; filtered_count reports how many (only present
        when something was dropped).
      - total_count = number of permitted elements Cascade returned in
        THIS response (NOT a true site-wide match count).
      - has_more = whether client-side truncation to `limit` actually dropped any.
    """
    limit = clamp_limit(limit)
    identifiers = [e for e in elements.flat if isinstance(e, IdentifierType)]
    permitted = [
        e for e in identifiers if security.is_asset_type_allowed(str(e.get_type))
    ]
    truncated = permitted[:limit]
    result: dict[str, Any] = {
        "results": [describe_element(e) for e in truncated],
        "total_count": len(permitted),
        "has_more": len(permitted) > limit,
    }
    dropped = len(identifiers) - len(permitted)
    if dropped:
        result["filtered_count"] = dropped
    return result


def truncate_list(
    items: list[Any],
    *,
    key: str,
    limit: int | None = None,
    expand_with: str | None = None,
) -> dict[str, Any]:
    """Cap a list for LLM consumption, wrapped under `key` with the same
    total_count/has_more shape `format_search_results` already established.

    When truncated and `expand_with` is given, surfaces it as a hint - same
    convention as the collapsed-field expand_with hints in `_collapse_value` -
    so an agent that needs the full picture knows where to get it in one call
    rather than discovering the detailed-mode fallback on its own.
    """
    limit = clamp_limit(limit)
    result: dict[str, Any] = {
        key: items[:limit],
        "total_count": len(items),
        "has_more": len(items) > limit,
    }
    if len(items) > limit and expand_with:
        result["expand_with"] = expand_with
    return result


def sort_by_relevance(names: list[str], guess: str) -> list[str]:
    """Names containing `guess` (case-insensitive) sort first, alphabetically
    among themselves; the rest follow, also alphabetically.

    Used for "not found, did you mean" listings, where the agent's own failed
    guess is a free relevance signal - concentrates the truncation-hides-the-
    target risk fix exactly where it matters (a failed lookup), rather than
    guessing at general-purpose relevance.
    """
    guess_lower = guess.lower()
    matches = sorted(n for n in names if guess_lower in n.lower())
    rest = sorted(n for n in names if guess_lower not in n.lower())
    return matches + rest


def format_names_for_message(
    names: list[str], *, limit: int = DEFAULT_LIMIT
) -> str:
    """Join names for embedding in a self-correcting ToolError message, capped."""
    shown = ", ".join(names[:limit])
    if len(names) > limit:
        shown += f", and {len(names) - limit} more"
    return shown

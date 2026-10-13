"""Centralized asset-type allowlist/blocklist, shared by the MCP server (this
package) and the skill validator (build_release.py copies this module's
lists into the built skill bundle at build time - see its
`write_security_gate()` - since a shipped skill bundle has no runtime
dependency on this package).

Fail-closed by design: `ALLOWED_ASSET_TYPES` is a **static snapshot** of
`cascade_cms.cmstypes.AssetTypes`'s real values (captured against
cascade-cms-rest 3.1.3), not derived from whatever version happens to be
installed. A future library release that adds a new asset type does not
silently become accessible here - it stays blocked (not in the allowlist)
until someone deliberately reviews and adds it. Re-derive this list with:

    python -c "
    import cascade_cms.cmstypes as m, typing
    def flatten(a):
        out = []
        for v in typing.get_args(a.__value__):
            out.extend(flatten(v) if isinstance(v, typing.TypeAliasType) else [v])
        return out
    print(sorted(flatten(m.AssetTypes)))
    "

BLOCKED_ASSET_TYPES exists to protect confidential information: `user`,
`group`, `role` carry usernames/hashed passwords/permission matrices;
`message` carries system/workflow messages not related to content or
structure; `audit`/`activity` are the activity-stream records of who did
what. Nothing in this module ever wraps a write operation - allowlist
enforcement is a read gate, matching every tool in this server.

Identity fields (`MASKED_FIELDS`, e.g. `createdBy`/`lastModifiedBy`) are
masked wherever they appear in asset payloads returned to the caller, and
references to blocked types are dropped from query results.
"""

from __future__ import annotations

from typing import Any

BLOCKED_ASSET_TYPES: tuple[str, ...] = (
    "activity",
    "audit",
    "group",
    "message",
    "role",
    "user",
)

REDACTED = "[REDACTED]"

# Keys whose values name a person. Compared case-insensitively, at any
# depth. Confirm additions against a real asset with
# cascade_query_asset(..., 'find("<key>")').
MASKED_FIELDS: tuple[str, ...] = (
    # group/user name lists (site roleAssignments, workflow definitions)
    "applicableGroupNames",
    "applicableGroups",
    "groups",
    "users",
    # people
    "author",
    "createdBy",
    "lastModifiedBy",
    "lastPublishedBy",
    "modifiedBy",
    "owner",
    "reviewer",
)

# Every other real AssetTypes value, as of cascade-cms-rest 3.1.3. Allowlist
# semantics expressed over the full real type set (not a narrow curated
# subset) so this doesn't break any existing template or MCP tool usage,
# while still failing closed for asset types this list doesn't know about.
ALLOWED_ASSET_TYPES: tuple[str, ...] = (
    "assetfactory",
    "assetfactorycontainer",
    "block",
    "block_FEED",
    "block_INDEX",
    "block_TEXT",
    "block_TWITTER_FEED",
    "block_XHTML_DATADEFINITION",
    "block_XML",
    "connectorcontainer",
    "contenttype",
    "contenttypecontainer",
    "datadefinition",
    "datadefinitioncontainer",
    "destination",
    "editorconfiguration",
    "facebookconnector",
    "file",
    "folder",
    "format",
    "format_SCRIPT",
    "format_XSLT",
    "googleanalyticsconnector",
    "metadataset",
    "metadatasetcontainer",
    "page",
    "pageconfiguration",
    "pageconfigurationset",
    "pageconfigurationsetcontainer",
    "pageregion",
    "publishset",
    "publishsetcontainer",
    "reference",
    "sharedfield",
    "sharedfieldcontainer",
    "site",
    "sitedestinationcontainer",
    "structureddatadefinition",
    "structureddatadefinitioncontainer",
    "symlink",
    "target",
    "template",
    "transport",
    "transport_cloud",
    "transport_db",
    "transport_fs",
    "transport_ftp",
    "transportcontainer",
    "twitterconnector",
    "wordpressconnector",
    "workflow",
    "workflowdefinition",
    "workflowdefinitioncontainer",
    "workflowemail",
    "workflowemailcontainer",
)


# Compared case-insensitively on both sides; the tuples above stay the
# source of truth (they keep the library's real mixed-case values).
_BLOCKED_FOLDED = frozenset(t.casefold() for t in BLOCKED_ASSET_TYPES)
_ALLOWED_FOLDED = frozenset(t.casefold() for t in ALLOWED_ASSET_TYPES)
_MASKED_FOLDED = frozenset(f.casefold() for f in MASKED_FIELDS)

_PLURALS = {
    "activities": "activity",
    "audits": "audit",
    "groups": "group",
    "messages": "message",
    "roles": "role",
    "users": "user",
}


def normalize_asset_type(asset_type: str) -> str:
    """Trim, casefold and fold the plural forms of blocked types
    ('users' -> 'user') so aliases hit the blocklist, not just the
    allowlist's 'unknown type' path."""
    folded = asset_type.strip().casefold()
    return _PLURALS.get(folded, folded)


def is_asset_type_blocked(asset_type: str) -> bool:
    return normalize_asset_type(asset_type) in _BLOCKED_FOLDED


def is_asset_type_allowed(asset_type: str) -> bool:
    return normalize_asset_type(asset_type) in _ALLOWED_FOLDED


def is_guarded_term(term: str) -> bool:
    """True when `term` is exactly a blocked type (or plural) or a masked
    field name - a search for it is a probe for identity data."""
    folded = term.strip().casefold()
    return is_asset_type_blocked(folded) or folded in _MASKED_FOLDED


def mask_identity_fields(data: Any) -> Any:
    """Deep copy of `data` with every MASKED_FIELDS value replaced by
    REDACTED, at any depth. The key is kept so the asset shape is intact."""
    if isinstance(data, dict):
        return {
            key: (
                REDACTED
                if isinstance(key, str)
                and key.casefold() in _MASKED_FOLDED
                else mask_identity_fields(value)
            )
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [mask_identity_fields(item) for item in data]
    return data


# Top-level fields masked wholesale for one asset type, because they carry
# user/group names inside a single string (a workflow definition's xml
# names recipient, assigned and default groups).
MASKED_FIELDS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "workflowdefinition": ("xml",),
}


def mask_asset(data: dict[str, Any], asset_type: str | None) -> dict[str, Any]:
    """mask_identity_fields plus the type-specific fields above."""
    masked: dict[str, Any] = mask_identity_fields(data)
    for key in MASKED_FIELDS_BY_TYPE.get(
        (asset_type or "").casefold(), ()
    ):
        if key in masked:
            masked[key] = REDACTED
    return masked


def is_guarded_reference(value: Any) -> bool:
    """True for a dict whose `type` names a blocked asset type, e.g. an
    access-rights entry {"type": "user", "name": "..."}."""
    if not isinstance(value, dict):
        return False
    asset_type = value.get("type")
    return isinstance(asset_type, str) and is_asset_type_blocked(
        asset_type
    )


def prune_guarded_references(value: Any) -> Any:
    """Copy of `value` with every guarded reference removed from lists
    and dicts, at any depth. A guarded reference passed in directly is
    the caller's to drop (see is_guarded_reference)."""
    if isinstance(value, list):
        return [
            prune_guarded_references(item)
            for item in value
            if not is_guarded_reference(item)
        ]
    if isinstance(value, dict):
        return {
            key: prune_guarded_references(item)
            for key, item in value.items()
            if not is_guarded_reference(item)
        }
    return value

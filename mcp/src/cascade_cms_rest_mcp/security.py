"""Centralized asset-type allowlist/blocklist, shared by the MCP server (this
package) and the skill validator (skill/build_skill.py copies this module's
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
structure. Nothing in this module ever wraps a write operation - allowlist
enforcement is a read gate, matching every tool in this server.
"""

from __future__ import annotations

BLOCKED_ASSET_TYPES: tuple[str, ...] = (
    "group",
    "message",
    "role",
    "user",
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


def is_asset_type_blocked(asset_type: str) -> bool:
    return asset_type.lower() in BLOCKED_ASSET_TYPES


def is_asset_type_allowed(asset_type: str) -> bool:
    return asset_type.lower() in ALLOWED_ASSET_TYPES

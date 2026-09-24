"""Translate Cascade-level failures (CascadeError values, or a
CascadeBatchError raised by submit_requests) into self-correcting MCP ToolErrors. Every
message here names what was tried, what's actually available, and/or which
tool to call next - never a bare "not found" or raw traceback.
"""

from __future__ import annotations

import os
from typing import Any

from cascade_cms.cmstypes import Asset, CascadeError, IdentifierType, Path
from cascade_cms.failures import CascadeBatchError
from cascade_cms.utils.redaction import mask_token
from mcp.server.mcpserver.exceptions import ToolError

from . import security
from .formatting import format_names_for_message, sort_by_relevance


def scrub_token(text: str) -> str:
    """Replace the current CASCADE_API_KEY value with its masked form."""
    token = os.environ.get("CASCADE_API_KEY")
    if token:
        return text.replace(token, mask_token(token))
    return text


def _tool_error(message: str) -> ToolError:
    """Every ToolError built here passes through the token scrub."""
    return ToolError(scrub_token(message))


def describe_identifier(identifier: IdentifierType | Path) -> str:
    if isinstance(identifier, IdentifierType):
        return f"{identifier.get_type} {identifier.get_id}"
    return f"{identifier.asset_type} at {identifier.site_name}:{identifier.path}"


def single_result(results: list[Any], *, context: str) -> Any:
    """Unwrap a one-chain `submit_requests()` result.

    A batch-level failure raises CascadeBatchError (translated by
    `unexpected_failure_error`), so an empty result is now only possible
    for an empty queue; this still raises a ToolError rather than letting
    `results[0]` raise a bare IndexError.
    """
    if not results:
        raise _tool_error(
            f"{context}: no response was received from Cascade - this usually means a "
            "connectivity or session-level failure rather than a bad request. Check "
            "CASCADE_URL and CASCADE_API_KEY, confirm the server is reachable, and retry."
        )
    return results[0]


def search_failure_error(result: CascadeError | Exception) -> ToolError:
    if isinstance(result, CascadeError):
        message = (
            result.message
            or "Cascade reported a search failure with no further detail."
        )
        return _tool_error(f"cascade_search failed: {message}")
    return _tool_error(
        f"cascade_search failed unexpectedly ({result}). This usually indicates a "
        "connectivity/credential problem rather than a bad query - check CASCADE_URL "
        "and CASCADE_API_KEY."
    )


def blocked_asset_type_error(asset_type: str, *, context: str) -> ToolError:
    if security.is_asset_type_blocked(asset_type):
        return _tool_error(
            f"{context}: asset type '{asset_type}' is not accessible via this server. "
            "Access to users, groups, roles, and messages is restricted to protect "
            "confidential information (usernames, hashed passwords, permission "
            "matrices). If you need to work with permissions or user management, "
            "describe the requirement to the user and ask them to handle it "
            "manually rather than through this tool."
        )
    return _tool_error(
        f"{context}: asset type '{asset_type}' is not currently supported by this "
        "server's allowlist. If this is a real Cascade asset type that should be "
        "accessible, it needs to be added to ALLOWED_ASSET_TYPES in "
        "cascade_cms_rest_mcp/security.py."
    )


def read_asset_error(
    identifier: IdentifierType | Path,
    result: CascadeError | Exception,
    *,
    context: str = "cascade_read_asset",
    purpose: str | None = None,
) -> ToolError:
    described = describe_identifier(identifier)
    target = f" ({purpose})" if purpose else ""
    if isinstance(result, CascadeError):
        message = result.message or "asset not found"
        return _tool_error(
            f"{context} failed to read {described}{target}: {message}. "
            "Try cascade_search first to confirm the correct id/type/path, then retry "
            "cascade_read_asset with its result."
        )
    return _tool_error(
        f"{context} failed unexpectedly reading {described}{target} ({result}). This usually "
        "indicates a connectivity/credential problem - check CASCADE_URL and CASCADE_API_KEY."
    )


def no_resolvable_reference_error(
    asset: Asset, tried_fields: list[str], *, context: str
) -> ToolError:
    tried = ", ".join(tried_fields)
    available = format_names_for_message(sorted(asset._data.keys())) or "(none)"
    return _tool_error(
        f"{context}: could not resolve a reference from this asset - tried field(s) {tried}, "
        f"none present. Fields actually on this asset: {available}. Try "
        'cascade_read_asset(format="detailed") to inspect it directly.'
    )


def no_xml_field_error(data_definition: Asset, *, context: str) -> ToolError:
    return _tool_error(
        f"{context}: data definition {data_definition.get('id')} has no 'xml' field, so its "
        'schema can\'t be parsed. Try cascade_read_asset(format="detailed") on it directly to '
        "inspect what it actually contains."
    )


def group_not_found_error(
    data_definition: Asset, available_groups: list[str], group: str, *, context: str
) -> ToolError:
    available = (
        format_names_for_message(sort_by_relevance(available_groups, group)) or "(none)"
    )
    return _tool_error(
        f"{context}: group '{group}' not found in data definition "
        f"{data_definition.get('id')}. Available groups: {available}."
    )


def node_not_found_error(
    data_definition: Asset,
    group: str,
    available_identifiers: list[str],
    node_identifier: str,
    *,
    context: str,
) -> ToolError:
    available = (
        format_names_for_message(
            sort_by_relevance(available_identifiers, node_identifier)
        )
        or "(none)"
    )
    return _tool_error(
        f"{context}: field '{node_identifier}' not found in group '{group}' of data definition "
        f"{data_definition.get('id')}. Available fields in this group: {available}."
    )


def config_name_not_found_error(
    content_type: Asset,
    available_names: list[str],
    configuration_name: str,
    *,
    context: str,
) -> ToolError:
    available = (
        format_names_for_message(sort_by_relevance(available_names, configuration_name))
        or "(none)"
    )
    return _tool_error(
        f"{context}: page configuration '{configuration_name}' not found for content type "
        f"{content_type.get('name')}. Available configurations: {available}."
    )


def page_region_not_found_error(
    asset: Asset,
    configuration_name: str,
    page_region: str,
    available_regions: list[str],
    *,
    context: str,
) -> ToolError:
    available = (
        format_names_for_message(sort_by_relevance(available_regions, page_region))
        or "(none)"
    )
    return _tool_error(
        f"{context}: region '{page_region}' not found in configuration '{configuration_name}' "
        f"on this asset instance. This can mean the configuration name is valid but this "
        f"particular asset was never authored with content for this region, not that the name "
        f"is wrong. Regions present on this instance: {available}."
    )


def page_region_requires_configuration_name_error(*, context: str) -> ToolError:
    return _tool_error(
        f"{context}: page_region was given without configuration_name - a region only makes "
        "sense within a specific configuration. Supply configuration_name too, or omit "
        "page_region to list available configurations first."
    )


def invalid_query_error(query: str, reason: str, *, context: str) -> ToolError:
    return _tool_error(
        f"{context}: query {query!r} is not valid - {reason}. Examples of valid "
        'queries: \'metadata.dynamicFields[0].value\', \'metadata["dynamicFields"][0]\', '
        '\'metadata["*"]\' (wildcard over a list/dict), \'find("identifier")\' (search '
        "the whole asset for a key by name, at any depth)."
    )


def not_a_site_error(asset: Asset, *, context: str) -> ToolError:
    return _tool_error(
        f"{context}: expected a site asset, but read a '{asset.internal_type}' asset "
        f"({asset.get('name')!r}) instead. Root container ids only exist on site assets - "
        "pass the identifier/path of the site itself."
    )


def no_root_container_error(site: Asset, asset_type: str, *, context: str) -> ToolError:
    available = format_names_for_message(sorted(Asset._ROOT_CONTAINER_FIELDS.keys()))
    return _tool_error(
        f"{context}: '{asset_type}' has no known root container field on site "
        f"{site.get('name')!r}. Supported asset_type values: {available}."
    )


def list_sites_failure_error(result: CascadeError | Exception) -> ToolError:
    if isinstance(result, CascadeError):
        message = (
            result.message
            or "Cascade reported a listSites failure with no further detail."
        )
        return _tool_error(f"cascade_list_sites failed: {message}")
    return _tool_error(
        f"cascade_list_sites failed unexpectedly ({result}). This usually indicates a "
        "connectivity/credential problem - check CASCADE_URL and CASCADE_API_KEY."
    )


def unexpected_failure_error(tool_name: str, exc: Exception) -> ToolError:
    """Last-resort translation so no tool body can let a raw traceback leak."""
    if isinstance(exc, CascadeBatchError):
        return batch_failure_error(tool_name, exc)
    return _tool_error(f"{tool_name} failed unexpectedly: {exc}")


def batch_failure_error(tool_name: str, exc: CascadeBatchError) -> ToolError:
    cause = exc.__cause__
    detail = f"{type(cause).__name__}: {cause}" if cause else str(exc)
    return _tool_error(
        f"{tool_name} failed: the request batch could not be completed "
        f"({detail}). This usually indicates a connectivity/credential "
        "problem - check CASCADE_URL and CASCADE_API_KEY, confirm the "
        "server is reachable, and retry."
    )

# cascade-cms-rest-mcp

A local, read-only [MCP](https://modelcontextprotocol.io) server exposing a
Hannon Hill Cascade CMS server to MCP clients (Claude Desktop, Claude Code,
etc.), built on top of [`cascade-cms-rest`](https://pypi.org/project/cascade-cms-rest/).

Six tools, all read-only — no tool in this server can perform a write
operation, even indirectly:

| Tool | Purpose |
|---|---|
| `cascade_search` | Search a site for assets by text |
| `cascade_read_asset` | Read a single asset by id or by site+path |
| `cascade_get_data_structure` | A data-bound asset's field schema, resolved from its bound content type/data definition |
| `cascade_get_page_config` | A data-bound asset's page configuration names/regions |
| `cascade_root_container_id` | The root container id (e.g. Data Definitions folder) for an asset type on a site |
| `cascade_list_sites` | List every site on the server |

`cascade_get_data_structure` and `cascade_get_page_config` are
**schema-authoritative**: they resolve field/group/config names from the
asset's *bound content type or data definition*, not by sampling the one
asset instance you point them at — so the result is the full schema-valid
set, not just whatever happens to be populated on that instance.

This is a different, easily-confused thing from the *library's*
`Asset.get_data_structure()` method (used inside generated scripts, not by
this server) — that one is instance/leaf-only. See the skill's
`references/asset_api.md` for that distinction, and note that this server is
read-only by design: *writing* structured data still goes through the
skill's script-writing path (see its `callback-structured-data-edit.py`
template).

## Known limitation

`resolve_data_definition()` (`src/cascade_cms_rest_mcp/resolution.py`)
resolves a data-bound asset's data definition two ways: via
`contentTypeId → contentType.dataDefinitionId` (confirmed against a real
payload), and via a direct `dataDefinitionId` field on the asset itself
(present in the code as a fallback, but not yet confirmed against any real
fixture — harmless no-op if the field is absent). If you hit a data-bound
asset where resolution fails unexpectedly, this direct-field path is the
first thing to check.

## Configuration

Required environment variables (same names `CascadeWrapperBase` already
expects — no new credential-naming surface):

| Variable | Required | Purpose |
|---|---|---|
| `CASCADE_API_KEY` | Yes | Cascade API key |
| `CASCADE_URL` | Yes | e.g. `https://your-cascade-host:8443` |
| `SERVER` | No | Cosmetic — log-file naming, defaults to `default` |
| `CASCADE_MCP_CACHE_DIR` | No | Overrides the default `~/.cache/cascade-cms-mcp` response-cache location |

The server fails fast at startup (not on first tool call) if `CASCADE_API_KEY`
or `CASCADE_URL` is missing.

## Client configuration

Download and unpack a [release artifact](dist/) (built via `build_release.py`
— see the repo root `AGENTS.md`), then point your MCP client at it:

```json
{
  "mcpServers": {
    "cascade-cms": {
      "command": "uvx",
      "args": ["--from", "/path/to/unpacked/cascade-cms-rest-mcp", "cascade-cms-rest-mcp"],
      "env": {
        "CASCADE_API_KEY": "...",
        "CASCADE_URL": "https://your-cascade-host:8443"
      }
    }
  }
}
```

## Development

```bash
pip install -e "./mcp[dev]"   # from the repo root
pytest
ruff check .
mypy mcp/src/
```

`tests/smoke_test.py` is a manual, human-run script against a real dev
Cascade site (not collected by pytest) — see its own docstring.

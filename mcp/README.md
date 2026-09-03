# cascade-cms-rest-mcp

A local, read-only [MCP](https://modelcontextprotocol.io) server exposing a
Hannon Hill Cascade CMS server to MCP clients (Claude Desktop, Claude Code,
etc.), built on top of [`cascade-cms-rest`](https://pypi.org/project/cascade-cms-rest/).

Seven tools, all read-only — no tool in this server can perform a write
operation, even indirectly:

| Tool | Purpose |
|---|---|
| `cascade_search` | Search a site for assets by text |
| `cascade_read_asset` | Read a single asset by id or by site+path |
| `cascade_get_data_structure` | A data-bound asset's field schema, resolved from its bound content type/data definition |
| `cascade_get_page_config` | A data-bound asset's page configuration names/regions |
| `cascade_root_container_id` | The root container id (e.g. Data Definitions folder) for an asset type on a site |
| `cascade_list_sites` | List every site on the server |

## Known limitation

`cascade_get_data_structure` and `cascade_get_page_config` currently report
field/group/config names by sampling the *one asset instance* you point them
at — not the full schema-valid set the asset's type actually allows. See
`MCP_IMPLEMENTATION_PLAN_REV.md` §7 in the `py-cascade-cms` repo for the
deferred schema-authoritative design this is expected to move to.

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

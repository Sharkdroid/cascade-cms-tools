# cascade-cms-tools

Tooling built on top of [`cascade-cms-rest`](https://github.com/Sharkdroid/py-cascade-cms)
(the Hannon Hill Cascade CMS REST client library) — kept in its own repo so
the library itself stays a clean, dependency-light package.

| Directory | What it is |
|---|---|
| [`mcp/`](mcp/) | A local, read-only MCP server exposing a Cascade CMS server to MCP clients (Claude Desktop, Claude Code, etc.) |
| [`skill/`](skill/) | `cascade-script-writer`/`cascade-script-writer-lite` — Claude Code skills for writing scripts against `cascade-cms-rest` |

Both depend on the **published** `cascade-cms-rest` package (PyPI), not a
vendored copy — see each directory's own docs for how it's kept in sync.

## Development

```bash
pip install -e "./mcp[dev]"
pytest
ruff check .
mypy mcp/src/
```

See `AGENTS.md` for the skill-authoring workflow and how to rebuild release
artifacts for both `mcp/` and `skill/`.

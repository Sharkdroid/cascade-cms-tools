# cascade-cms-tools

Currently built against [`cascade-cms-rest`](https://github.com/Sharkdroid/py-cascade-cms) 3.2.2.

Tooling built on top of `cascade-cms-rest`
(the Hannon Hill Cascade CMS REST client library) — kept in its own repo so
the library itself stays a clean, dependency-light package.

| Directory | What it is |
|---|---|
| [`mcp/`](mcp/) | A local, read-only MCP server exposing a Cascade CMS server to MCP clients (Claude Desktop, Claude Code, etc.) |
| [`skill/`](skill/) | `cascade-script-writer` — a Claude Code skill for writing scripts against `cascade-cms-rest` |

Both depend on the **published** `cascade-cms-rest` package (PyPI), not a
vendored copy — see each directory's own docs for how it's kept in sync.

They're distributed separately: the MCP server is published to PyPI as
[`cascade-cms-rest-mcp`](https://pypi.org/project/cascade-cms-rest-mcp/),
and the skill ships as its own versioned zip on
[Releases](../../releases) (or build it yourself, `python build_release.py`,
see `AGENTS.md`). Neither requires the other at runtime — use just the
skill, just the MCP server, or both.

## How to use

1. **Set up the MCP server** (optional, works with any MCP client — Claude
   Code, Claude Desktop, or otherwise): `pip install cascade-cms-rest-mcp`
   (or run it via `uvx cascade-cms-rest-mcp`) and point your client's MCP
   config at it. See [`mcp/README.md`](mcp/README.md#client-configuration)
   for the exact config block and required environment variables
   (`CASCADE_API_KEY`, `CASCADE_URL`).

2. **Install the skill** (optional, Claude-specific — install whichever way
   matches your client). Download the latest
   `cascade-cms-tools-skill-<version>.zip` from [Releases](../../releases)
   and unpack it, or build it yourself (`python build_release.py`); you get
   a `cascade-cms-tools/skill/cascade-script-writer/` folder.
   - **Claude Code**: copy `cascade-script-writer/` into
     `.claude/skills/cascade-script-writer/` (project-level, for team
     sharing) or `~/.claude/skills/cascade-script-writer/` (personal).
   - **Claude Desktop / claude.ai**: re-zip just the
     `cascade-script-writer/` folder (so the zip's top level is the
     `cascade-script-writer/` folder itself, not the outer
     `cascade-cms-tools/` wrapper) and upload it via **Customize → Skills →
     Upload a skill**.

3. **Use it.** Ask Claude to write a script against `cascade-cms-rest` for
   whatever asset-management task you have — see "What this is for" below
   for the tasks this tooling is aimed at, and `skill/cascade-script-writer/SKILL.md`
   for the full workflow the skill follows.

## What this is for

The skill and MCP server exist for **multi-step business-logic scripts** —
create-then-edit pipelines, callback-driven batch processing, workflow
orchestration — and for power users whose script requirements change often
enough that repeatedly re-deriving correct `cascade-cms-rest` API usage by
hand is the real recurring cost.

Writing directly against `cascade-cms-rest` — no skill, no MCP, no agent —
remains fully supported and is often the better choice for a simple, one-off
script. If that's your situation, you may not need this tooling at all.

There used to be a smaller "lite" variant of the skill for weak/fast models;
it's gone. See [`docs/why-no-lite-skill.md`](docs/why-no-lite-skill.md) for
why, and [`docs/model-requirements.md`](docs/model-requirements.md) for the
model-capability floor this tooling assumes and free-vs-paid guidance.

## Security & scope

Both the MCP server and the skill validator enforce the same asset-type
allowlist (`mcp/src/cascade_cms_rest_mcp/security.py`, copied into the skill
bundle at build time): `user`, `group`, `role`, and `message` assets are
blocked, fail-closed, at both layers. This protects confidential information
— usernames, hashed passwords, permission matrices — that these asset types
can carry. An asset type this tooling doesn't yet know about is blocked by
default too, rather than allowed by default, until someone deliberately adds
it to the allowlist.

This is not a claim that the tooling covers every Cascade feature. Operations
that exist in the library but aren't wrapped by a template or an MCP tool
(permission validation, LDAP/authentication configuration, audit-log or
message introspection, workflow shapes beyond the `workflow-orchestration`
template) are meant to be described to the user and written by hand from
their description — see `SKILL.md`'s "Handling unsupported features" section
— rather than guessed at or silently skipped.

## Development

```bash
pip install -e "./mcp[dev]"
pytest
ruff check .
mypy mcp/src/
```

See `AGENTS.md` for the skill-authoring workflow and how to rebuild the
skill release bundle (`python build_release.py`).

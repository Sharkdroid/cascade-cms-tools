# AGENTS.md

`cascade-cms-tools` — the MCP server and script-writing skill for
[`cascade-cms-rest`](https://github.com/Sharkdroid/py-cascade-cms). Both
depend on the *published* `cascade-cms-rest` package; neither vendors a copy
of the library's source.

## Repo commands

```bash
pip install -e "./mcp[dev]"
pytest
ruff check .
mypy mcp/src/
```

CI runs all three. Run them before considering a change done.

## Writing scripts that use cascade-cms-rest

One skill, `skill/cascade-script-writer/` — 21 templates, full JSON schema.
There is no smaller "lite" variant; see `docs/why-no-lite-skill.md` for why,
and `docs/model-requirements.md` for the model-capability floor this skill
assumes. A companion read-only MCP server (`mcp/`) is also available for
schema questions — see "Cross-checking schema with the MCP server" below.

Start from a template:

```bash
cd skill/cascade-script-writer
python scripts/new_script.py --list
python scripts/new_script.py --template create-bulk --out my_script.py
```

Then validate:

```bash
python skill/cascade-script-writer/scripts/validate_script.py my_script.py
```

**A generated script is complete only when `validate_script.py` exits 0.** Fix
what it reports and re-run; cap at 3 attempts, then surface the output verbatim
rather than looping.

Two rules the validator enforces and scripts must never break:

- `CascadeWrapperBase` is the only entry point — no `cascade_cms.driver`, no
  manual asyncio event loop, no hand-built `aiohttp.ClientSession`.
- `Asset` fields are written by attribute (`asset.keywords = value`), never by
  subscript (`asset["keywords"] = value` raises `TypeError`).

## Cross-checking schema with the MCP server

When the `cascade-cms-rest-mcp` server (`mcp/`) is connected, prefer its
`cascade_get_data_structure` / `cascade_get_page_config` tools to confirm
valid field/group/configuration names before writing a script that
references them by name, rather than guessing from
`Asset.get_data_structure()`'s instance-sampling result. See
`references/asset_api.md` in the skill and `mcp/README.md` for the
distinction between the two same-named-but-different `get_data_structure`s.
The skill remains fully usable without the MCP server connected — this is a
preference, not a dependency.

## Rebuilding the skill

```bash
pip install --upgrade cascade-cms-rest   # first, if you want to bundle a newly-released version
python skill/build_skill.py
```

Syncs the *installed* `cascade-cms-rest` package into the skill bundle
(this repo holds no copy of the library's source — see `skill/build_skill.py`'s
`sync_snapshot()`), rewrites the manifest, validates every template, and zips.
Never copy the snapshot by hand — a stale bundle makes the validator reject
correct scripts.

The `.skill` zip filename uses **cascade-cms-tools' own v0.x.x version**
(read from `mcp/pyproject.toml`, shared with the mcp package and the git
release tag — see "Cutting a release" below), not the bundled library's
version. The library version bundled inside (recorded in
`cascade_cms/_bundle_manifest.json`) is a separate number — when it changes,
also update the "Currently built against `cascade-cms-rest`..." line at the
top of the repo root `README.md` by hand; nothing regenerates it
automatically.

`build_skill.py` only syncs, validates, and zips — it cannot write or repair
a template. `.github/workflows/release.yml` runs it unattended on every
`v*.*.*` tag (re-syncing against whatever `cascade-cms-rest` is installed
there and re-validating every template) as a release gate, same as it runs
`ruff`/`mypy`/`pytest` — a failure there blocks the release exactly like any
other failing check. But when a `cascade-cms-rest` release breaks a
template's API usage (a renamed method, a changed signature, a different
execution model — anything `validate_script.py` would reject), *fixing* it
requires understanding the new API well enough to teach it correctly. That
part is agent/human judgment work no CI step can do — rewrite the affected
template by hand locally, confirm `build_skill.py` passes, then commit and
re-tag.

## Rebuilding the MCP release artifact

```bash
python mcp/build_release.py
```

Zips `mcp/`'s installable project (`pyproject.toml`, `README.md`,
`src/cascade_cms_rest_mcp/`) into a versioned archive under `mcp/dist/`,
committed into the repo the same way `skill/*.skill` files are. Not published
to PyPI — see `mcp/README.md` for how an end user consumes the artifact
(`uvx --from <unpacked-dir> cascade-cms-rest-mcp`).

**`mcp/pyproject.toml`'s `version` is cascade-cms-tools' one shared v0.x.x
number** — `skill/build_skill.py` reads the same field for the `.skill` zip
filename (`read_tools_version()`), so bumping it here is the single place
that moves both artifacts' version at once. It is deliberately independent
of whatever `cascade-cms-rest` version is actually installed/bundled (that's
tracked separately — see "Rebuilding the skill" above). Bump it, run both
build scripts, commit the resulting zips, then tag:

## Cutting a release

```bash
git tag v0.2.0   # matches mcp/pyproject.toml's version - one tag covers both skill/ and mcp/
git push origin v0.2.0
```

`.github/workflows/release.yml` then re-syncs/re-validates the skill bundle
and the MCP package against whatever `cascade-cms-rest` is installed (see
the two sections above), runs `ruff`/`mypy`/`pytest`, and — only if all of
that passes — creates a GitHub release attaching **every** currently-tracked
`skill/*.skill` and `mcp/dist/*.zip` file (this repo keeps full build
history committed, not just the latest of each). So: rebuild+commit
whichever of `skill/`/`mcp/` actually changed (per the two sections above)
*before* tagging — the tag doesn't trigger a rebuild-and-commit, only a
validate-and-publish-what's-there.

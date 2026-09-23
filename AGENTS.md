# AGENTS.md

`cascade-cms-tools` — the MCP server and script-writing skill for
[`cascade-cms-rest`](https://github.com/Sharkdroid/py-cascade-cms). Both
depend on the *published* `cascade-cms-rest` package; neither vendors a copy
of the library's source.

## Environment

All commands below run in the repo-local conda env, `./.conda` (gitignored):

```bash
conda create -y -p ./.conda python=3.13
./.conda/bin/pip install --upgrade cascade-cms-rest ruff
```

Some machines use `./.venv` instead (same commands, substitute
`./.venv/bin/...` for `./.conda/bin/...`). Use whichever of the two
exists in your checkout.

`build_release.py` bundles whatever `cascade-cms-rest` is *installed*, so
always run it with `./.conda/bin/python`.

## Repo commands

```bash
pip install -e "./mcp[dev]"
pytest
ruff check .
mypy mcp/src/
```

CI runs all three. Run them before considering a change done.

## Writing scripts that use cascade-cms-rest

One skill, `skill/cascade-script-writer/` — 20 templates, full JSON schema.
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

Four rules the validator enforces and scripts must never break:

- `CascadeWrapperBase` is the only entry point — no `cascade_cms.driver`, no
  manual asyncio event loop, no hand-built `aiohttp.ClientSession`.
- `Asset` fields are written by attribute (`asset.keywords = value`), never by
  subscript (`asset["keywords"] = value` raises `TypeError`).
- Everything is type-hinted: every function parameter and return, and every
  module-level variable (`environment_variables: EnvironmentVars = {...}`).
- No line is longer than 60 characters — code, comments and docstrings.
  **Never hand-wrap code.** After writing or editing a script, run
  `./.conda/bin/ruff format --line-length 60 --isolated my_script.py`
  *before* validating. Ruff cannot split strings, comments or
  docstrings, so hand-wrap only the lines `validate_script.py` still
  reports (and keep those short as you write them).

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

## Rebuilding the release bundle

```bash
./.conda/bin/pip install --upgrade cascade-cms-rest   # first, to bundle a newly-released version
./.conda/bin/python build_release.py
```

One artifact, `dist/cascade-cms-tools-skill-<version>.zip`, containing just
the skill plus the root `README.md`/`LICENSE`. The MCP server (`mcp/`) is
no longer stapled into this zip — it's a separate, independently-published
PyPI package (`cascade-cms-rest-mcp`), published straight from `mcp/` by
`.github/workflows/release.yml`'s `publish-pypi` job on every `v*.*.*` tag
(see "Cutting a release" below). The build syncs the *installed*
`cascade-cms-rest` package into the skill (this repo holds no copy of the
library's source — see `build_release.py`'s `sync_skill_snapshot()`),
rewrites the manifest, validates every template, and zips it up. Never copy
the skill snapshot by hand — a stale bundle makes the validator reject
correct scripts.

The zip filename and the library version bundled inside are deliberately
different numbers:

- **Tools version** — cascade-cms-tools' own v0.x.x line, read from
  `mcp/pyproject.toml` (shared with the mcp package and the git release
  tag — see "Cutting a release" below). Names the zip.
- **Library version** — the `cascade-cms-rest` version actually bundled,
  recorded in `cascade_cms/_bundle_manifest.json`. When it changes, also
  update the "Currently built against `cascade-cms-rest`..." line at the
  top of the repo root `README.md` by hand; nothing regenerates it
  automatically.

`build_release.py` only syncs, validates, and zips — it cannot write or
repair a template. `.github/workflows/release.yml` runs it unattended on
every `v*.*.*` tag (re-syncing against whatever `cascade-cms-rest` is
installed there and re-validating every template) as a release gate, same
as it runs `ruff`/`mypy`/`pytest` — a failure there blocks the release
exactly like any other failing check. But when a `cascade-cms-rest` release
breaks a template's API usage (a renamed method, a changed signature, a
different execution model — anything `validate_script.py` would reject),
*fixing* it requires understanding the new API well enough to teach it
correctly. That part is agent/human judgment work no CI step can do —
rewrite the affected template by hand locally, confirm `build_release.py`
passes, then commit and re-tag.

## Cutting a release

```bash
git tag v0.2.0   # matches mcp/pyproject.toml's version
git push origin v0.2.0
```

`.github/workflows/release.yml` then re-syncs/re-validates the skill bundle
against whatever `cascade-cms-rest` is installed (see the section above),
runs `ruff`/`mypy`/`pytest`, and — only if all of that passes — runs two
jobs in parallel:

- **`release`** creates a GitHub release attaching only this tag's
  `dist/cascade-cms-tools-skill-<version>.zip` (not the full history kept
  in `dist/`). So: rebuild+commit (`python build_release.py`, then commit
  the resulting zip) *before* tagging — the tag doesn't trigger a
  rebuild-and-commit, only a validate-and-publish-what's-there.
- **`publish-pypi`** builds `mcp/` (`python -m build ./mcp`) and publishes
  it to PyPI as `cascade-cms-rest-mcp` via Trusted Publishing (OIDC) — no
  API token stored in the repo. This requires the repo to be registered as
  a trusted publisher for the `pypi` GitHub Environment on PyPI's project
  settings (one-time, done on pypi.org, not in this repo) before the first
  tag that should actually publish.

---
name: cascade-script-writer
description: Generate standalone Python scripts that use the cascade_cms library (a custom REST client for Hannon Hill Cascade CMS) to accomplish a specific asset-management task the user describes — e.g. "create assets from a CSV", "publish all pages under a folder", "read a page and update its content", "advance assets through a workflow". Use this whenever the user asks for a script, automation, or one-off tool that reads, creates, edits, deletes, copies, moves, publishes, or otherwise manipulates Cascade CMS assets via this library. Always validate generated scripts with scripts/validate_script.py before presenting them — never hand over an unvalidated script.
---

# Cascade CMS Script Writer

Writes standalone Python scripts against the `cascade_cms` library. Every
script is checked against the **real bundled library source**, not against
notes in this file, before it reaches the user.

## Workflow

Follow these steps in order.

**Step 1 — Identify the task shape.** Determine: which operation(s), how the
target assets are named (UUID or site+path), what data drives the work (CSV,
hardcoded list, search results), and whether each result needs processing
(a `.then()` callback) or a plain loop suffices.

**Step 2 — Pick a template.** Read `templates/INDEX.md` and choose the row
matching the task shape. Do not write a script from scratch — the 21 templates
all pass the validator as written, so starting from one means only your
task-specific edits can break it.

```bash
python scripts/new_script.py --template create-bulk --out my_script.py
```

If no template fits, start from the closest one and replace the operation.

**Step 3 — Look up exact names.** Read `references/operations_schema.json` for
method signatures, payload fields, and aliases. Cascade payloads use aliases
(`parentFolderId` vs `parent_folder_id`) that must match exactly — never guess
a field name. For `Asset` reads/writes, read `references/asset_api.md`. When
the schema is not detailed enough, read the bundled source in `cascade_cms/`;
it is ground truth.

**Step 4 — Edit the script** for the specific task. Keep the template's
structure: config block, `main()`, `with CascadeWrapperBase(...)`, try/except
around `submit_requests()`. Keep every function, parameter and module-level
variable **type-hinted** and every line **60 characters or fewer** — see
"Script conventions" below. Templates already comply; your edits must too.

**Step 5 — Validate. This gate is mandatory.**

```bash
python scripts/validate_script.py my_script.py
```

The script is done **only when this exits 0**. If it fails, read the message —
each one names the bad symbol and the exact fix — apply the fix, and re-run.
Besides API checks, the validator enforces the two style rules below: missing
type hints and any line over 60 characters both fail it.

**Cap this at 3 attempts.** If it still fails after the third run, stop and
show the user the validator's output verbatim along with the current script.
Do not keep looping.

**Step 6 — Present** the script with a one-line note on what it does and which
environment variables it needs. If the script has runtime-dynamic values the
validator cannot check statically (CSV rows, search results), say so rather
than implying full coverage.

### Checklist

```
[ ] Template chosen from templates/INDEX.md
[ ] Field names/aliases confirmed in references/operations_schema.json
[ ] Only CascadeWrapperBase used — no driver, no event loop, no ClientSession
[ ] Asset writes use attribute assignment, not asset["x"] = ...
[ ] Path identifiers include siteName and asset_type
[ ] submit_requests() wrapped in try/except
[ ] Every param, return and module-level var is type-hinted
[ ] ruff format --line-length 60 --isolated run on the file
[ ] No line longer than 60 characters (code, comments, docstrings)
[ ] validate_script.py exits 0
```

## What the library actually does

**Queue, then submit.** `cascade.operations.<op>(...)` queues a request.
Nothing hits the network until `cascade.submit_requests()`, which runs the whole
batch concurrently and then clears the queue. One `submit_requests()` per batch.

**Results come back in COMPLETION order, not submission order.** Never zip
results against the request list by position, and never index into it —
identify each result from its own contents.

**Failures are values, not exceptions.** Any operation can return a
`CascadeError` (with `.message`) instead of its success type. Check with
`isinstance(result, CascadeError)` before using a result. Requests that fail at
the Python level are logged and *dropped*, so `len(results)` may be smaller
than the number queued.

**Write operations return `CascadeSuccess`.** `edit`, `delete`, `copy`, `move`,
`publish`, `checkIn`, `siteCopy`, `performWorkflowTransition`,
`editAccessRights`, `editWorkflowSettings`, `editPreference`, `markMessage`,
`deleteMessage` all return `CascadeSuccess` (`{"success": true}`) on success and
`CascadeError` on failure. `checkOut` is the exception — it returns
`CheckedOutAsset`. `read` returns `Asset`; `create` returns `IdentifierType`.
Both result types are strict as of `cascade-cms-rest` 3.1.6:
`CascadeSuccess.success` is `Literal[True]` and forbids extra keys,
`CascadeError.success` is `Literal[False]` — so `isinstance` is the reliable
discriminator, not a truthiness check on `.success`.

**`Asset` is written by attribute, not subscript.**

```python
asset.get("keywords")        # read
asset.keywords = "a, b"      # write
asset["keywords"] = "a, b"   # TypeError: no __setitem__
```

`Asset.__setattr__` also rejects a type change on an existing field
(`str` → `int` raises). Details in `references/asset_api.md`.

**`Asset.get()` takes dotted paths (3.1.6+).** `asset.get("a.b.c")` walks
nested dicts (max depth 5; deeper raises `ValueError`) and raises `KeyError`
when any segment is missing — there is no default argument, so guard with
`try/except KeyError` when a field may be absent. Use it for nested metadata
(`asset.get("metadata.dynamicFields")`), **not** for `structuredData` or
`pageConfigurations`: `get()` emits a warning for those roots. Use
`asset.get_data_structure(group, identifier)` and
`asset.get_page_configuration(name, region)` instead — they return live
references you can edit in place.

**UUIDs serialize as bare hex.** Cascade rejects dashed UUIDs, so
`IdentifierType.identifier`, `NewAsset.site_id` and `NewAsset.parent_folder_id`
emit `uuid.UUID.hex`. Pass real `uuid.UUID` objects and let the library format
them.

**`IdentifierType` forbids extra keys.** Only `id`, `type`, `recycled`, `path`
are accepted; anything else raises. `asset_type`/`identifier` work as aliases
for `type`/`id`.

**A `Path` identifier needs `siteName`.** It is a plain dict, so nothing
validates it until `resolve_identifier()` raises
`ValueError("Path identifiers require siteName to build the request URL")`.

**Callbacks** registered with `.then(fn)` or `.then([fn, ...])` run per result
after the batch: sequential per result, concurrent across results. Async
callbacks are awaited; sync callbacks run in an executor (`ThreadPoolExecutor`
by default — pass a `ProcessPoolExecutor` via `submit_requests(executor=...)`
for CPU-bound work). **A callback that raises is logged and swallowed**, so
track outcomes yourself if partial failure matters. Shared state touched from a
sync callback needs a `threading.Lock`.

## Script conventions

```python
#!/usr/bin/env python3
"""One-line description."""

import os
from typing import Any

from cascade_cms.cmstypes import Asset, CascadeError
from cascade_cms.wrapper import CascadeWrapperBase

# ----- Configuration -----
environment_variables: dict[str, str] = {
    "API_KEY": os.environ["CASCADE_API_KEY"],
    "CASCADE_URL": os.environ["CASCADE_URL"],
    "SERVER": os.environ.get("SERVER", "default"),
}
configuration_variables: dict[str, Any] = {
    "cache_name": "./cache/cache.sqlite",
    "allowed_codes": (200,),
    "allowed_methods": ("GET",),
}


def report(result: Asset | CascadeError) -> None:
    if isinstance(result, CascadeError):
        print(f"FAILED: {result.message}")
        return
    print(result.get("path"))


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read(...).then(report)

        try:
            cascade.submit_requests(Asset)
        except Exception as exc:
            print(f"Request submission failed: {exc}")


if __name__ == "__main__":
    main()
```

**Type hints are mandatory.** Every function and method parameter, every
return type (`-> None` when nothing is returned), every callback, nested
function and module-level variable carries an annotation. The config dicts
are `dict[str, str]` / `dict[str, Any]`, targets are
`list[IdentifierType]`, and a `.then()` callback taking a read result is
`Asset | CascadeError`. Only `self`/`cls` and lambdas are exempt.
`validate_script.py` fails the script on any gap, naming the line and symbol.

**Lines are at most 60 characters** — code, comments and docstrings alike.
**Do not hand-wrap code.** Write the script naturally, then run:

```bash
ruff format --line-length 60 --isolated my_script.py
```

Ruff re-wraps all code layout. It cannot split strings, comments or
docstrings, so afterwards hand-fix only the lines `validate_script.py`
still reports (keep comments and docstrings short as you write them, and
pull long f-string pieces into a local variable). The validator fails on
any line over 60 characters and runs `ruff format --check` with the same
flags when `ruff` is installed. (The old 150-character limit is retired.)

**`CascadeWrapperBase` is the only entry point.** Never import
`cascade_cms.driver` or anything from it (`CascadeCMSRestDriver`,
`RequestExecutor`, `CacheHandler`), never touch the event loop
(`new_event_loop`, `set_event_loop`, `run_until_complete`, `get_event_loop`),
never construct an `aiohttp.ClientSession`. The wrapper owns the loop and
session for the life of the `with` block and wires them into logging and
callback execution — bypassing it produces unclosed sessions, unlogged
requests, and an uncleared request queue.

Other conventions:

- **Config block, not a .env framework.** Show `API_KEY` / `CASCADE_URL` /
  `SERVER` as a block the user fills in however they like. Do not assume
  `python-dotenv` or any particular mechanism.
- **Wrap `submit_requests()` in try/except**, print the failure, return
  gracefully. An unhandled traceback should never be the only feedback.
- **Normal logging by default** — pass no `debug` argument unless the user asks
  for verbose output. Debug mode needs a fully specified config dict (every key,
  no inferred defaults); see `environment_and_config.debug_config` in the schema.
- **Comments explain why, not what.** Don't write `# read the asset` above a
  `read()` call. Do explain a UUID-vs-Path choice, a required alias, or why a
  callback runs in a process pool.
- **One `main()`**, guarded by `if __name__ == "__main__":`.
- **Nothing platform-specific.** The script must run in a bare `python3`
  interpreter (3.13+, matching the bundled library). Dependencies are
  `cascade_cms` plus stdlib.

## Examples

### Bulk create

```python
payloads: list[NewAsset] = [
    NewAsset(
        name=row["name"],
        asset_type="page",
        # Exactly one of site_name/site_id, and exactly one
        # of parent_folder_path/parent_folder_id.
        site_name="www",
        parent_folder_path=row["folder"],
        title=row["title"],  # extra fields pass through
    )
    for row in rows
]

with CascadeWrapperBase(
    environment_variables, configuration_variables
) as cascade:
    cascade.operations.create(payloads)
    try:
        results = cascade.submit_requests(IdentifierType)
    except Exception as exc:
        print(f"Request submission failed: {exc}")
        return

    for result in results:
        if isinstance(result, CascadeError):
            print(f"FAILED: {result.message}")
        else:
            kind, new_id = result.get_type, result.get_id
            print(f"Created {kind} {new_id}")
```

### Read, modify, save

```python
with CascadeWrapperBase(
    environment_variables, configuration_variables
) as cascade:
    cascade.operations.read(targets)
    assets = cascade.submit_requests(Asset)

    editable: list[Asset] = [
        a for a in assets if not isinstance(a, CascadeError)
    ]
    for asset in editable:
        # Attribute assignment, never asset[...] = ...
        asset.displayName = "Annual Report 2025"
        keywords: str = asset.get("keywords") or ""
        asset.keywords = keywords.strip().lower()

    if editable:
        cascade.operations.edit(editable)
        # A write operation resolves to CascadeSuccess.
        results = cascade.submit_requests(CascadeSuccess)
        for result in results:
            if isinstance(result, CascadeError):
                print(f"FAILED: {result.message}")
```

### Workflow transition with error handling

```python
with CascadeWrapperBase(
    environment_variables, configuration_variables
) as cascade:
    cascade.operations.readWorkflowInformation(target)
    try:
        infos = cascade.submit_requests(workflowInformation)
    except Exception as exc:
        print(f"Workflow read failed: {exc}")
        return

    for info in infos:
        if isinstance(info, CascadeError):
            print(f"FAILED: {info.message}")
            continue
        for step in info.ordered_steps:
            if step["label"] != info.current_step:
                continue
            for action in step["actions"]:
                if action["action_identifier"] != "approve":
                    continue
                transition = workflowTransitionInformation(
                    workflowId=info.workflow_info_id,
                    actionIdentifier="approve",
                    transitionComment="Advanced.",
                )
                ops = cascade.operations
                ops.performWorkflowTransition(
                    target, transition
                )

    for result in cascade.submit_requests(CascadeSuccess):
        if isinstance(result, CascadeError):
            print(f"FAILED: {result.message}")
```

## Reference files

Read these on demand — don't load them all up front.

| File | Read it when |
|---|---|
| `templates/INDEX.md` | Always, at Step 2 — pick a starting template |
| `templates/*.py` | 21 runnable, validator-passing scripts |
| `references/operations_schema.json` | You need a signature, field name, or alias |
| `references/asset_api.md` | The script reads or writes `Asset` fields |
| `cascade_cms/*.py` | The schema isn't specific enough — ground truth |
| `scripts/validate_script.py` | Every script, every time, before presenting |
| `scripts/new_script.py` | Scaffolding a script from a template |

## Model routing

Single-operation scripts built from a template are well within reach of a fast
model. Route multi-operation work, novel patterns, and anything not covered by
a template to a frontier model — the validator catches broken scripts, but it
cannot catch a script that is valid and solves the wrong problem.

## Keeping this skill in sync

The bundled `cascade_cms/` is a **snapshot** of the *installed*
`cascade-cms-rest` package (currently 3.1.6), so the validator can do real
Pydantic instantiation instead of schema lookups. A stale snapshot silently
rejects correct scripts, so never copy files by hand. From the repo root, in
the `.conda` environment:

```bash
./.conda/bin/pip install --upgrade cascade-cms-rest
./.conda/bin/python build_release.py            # sync, validate, zip
./.conda/bin/python build_release.py --no-zip   # sync + validate only
```

The build re-syncs the snapshot, rewrites `cascade_cms/_bundle_manifest.json`
(version + per-file sha256), validates all 21 templates, and **aborts if any
fails**. `validate_script.py` prints the bundled version on every run and warns
when the snapshot no longer matches its manifest.

If validation fails with `ModuleNotFoundError` for a library dependency:

```bash
pip install pydantic aiohttp aiohttp_client_cache aiosqlite typing_extensions
```

Install `ruff` (`pip install ruff`) and run `ruff format --line-length 60
--isolated <file>` before validating; with it installed the validator also
runs `ruff format --check --line-length 60`.

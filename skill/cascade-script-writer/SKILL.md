---
name: cascade-script-writer
description: Generate standalone Python scripts that use the cascade_cms library (a custom REST client for Hannon Hill Cascade CMS) to accomplish a specific asset-management task the user describes — e.g. "create assets from a CSV", "publish all pages under a folder", "read a page and update its content", "advance assets through a workflow". Use this only in a coding agent that can read and write the user's local project directory (for example Claude Code), not in a chat app. Use this whenever the user asks for a script, automation, or one-off tool that reads, creates, edits, deletes, copies, moves, publishes, or otherwise manipulates Cascade CMS assets via this library. Always validate generated scripts with scripts/validate_script.py before presenting them — never hand over an unvalidated script.
---

# Cascade CMS Script Writer

Writes standalone Python scripts against the `cascade_cms` library. Every
script is checked against the **real bundled library source**, not against
notes in this file, before it reaches the user.

## Before you start: coding agents only

This skill is used only by coding agents that can read and write the
user's local project directory, where scripts run and their log files
are written. If you cannot read that directory (for example in a chat
app, including one with its own sandbox), stop and tell the user this
skill needs Claude Code or an equivalent coding agent. For read-only
inspection from a chat app, use the Cascade MCP server instead.

Having a shell or sandbox is not enough; the test is access to the
directory where the user's script runs.

## Workflow

Follow these steps in order.

**Step 1 — Identify the task shape.** Determine: which operation(s), how the
target assets are named (UUID or site+path), what data drives the work (CSV,
hardcoded list, search results), and whether each result needs processing
(a `.then()` callback) or a plain loop suffices.

Also ask the user how they supply credentials and settings
(`API_KEY`, `CASCADE_URL`, `SERVER`, plus any script-specific values),
unless they already said. Offer the common choices: shell environment
variables read with `os.environ` (the templates' default), a `.env`
file they load themselves, or values typed into the config block. Do
not pick one silently, and never write a real API key into the script.

**Step 2 — Pick a template.** Read `templates/INDEX.md` and choose the row
matching the task shape. Do not write a script from scratch — the 19 templates
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
structure: config block, `main()`, `with CascadeWrapperBase(...)`, one
`submit_requests()` per batch. Keep every function, parameter and module-level
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

**Step 6 — Verify write operations in stages.** Applies to any script
containing a write operation: `create`, `edit`, `delete`, `copy`, `move`,
`publish`, `checkIn`, `checkOut`, `siteCopy`, `editAccessRights`,
`editWorkflowSettings`, `performWorkflowTransition`, `markMessage`,
`deleteMessage`, `editPreference`. Decide by operation, not HTTP method:
`search` is a POST but read-only. Read-only scripts skip this step.

Do not hand over a finished script with writes in one piece. This skill
never runs writes; the user runs each stage and the script's log file is
the evidence, which you read yourself. Build the script one write
operation at a time, in the order they run:

a. Tell the user the plan: the write operations in order, and that you
   will add them one at a time.
b. A stage contains ONLY its own write, plus the reads and
   payload-building callbacks that feed it. Earlier writes are not
   repeated; each is replaced by the identifier that stage's
   `[RESULT]` line logged. The library writes `[RESULT]` itself; the
   script does not need to log created identifiers. Validate it
   (Step 5).
c. The first run of any write uses ONE ITEM: one identifier, or one
   payload in a list `create` / `edit`. A folder or site counts as
   many; pick a leaf. Widen to the full list only after the stage
   passes.
d. Tell the user the exact command to run the paused stage, on a test
   asset or site where possible, and which assets the stage creates,
   changes or leaves behind, so they can clean up if you stop here.
e. After the user says it ran, read the log file yourself: the path is
   on the script's `[LOG]:` line, under the log directory. Proceed only
   if the log shows 0 failed and `[EXIT-CODE]: 0`, and the
   `[RESULT]` line is what you expected. Take the asset type and id
   from it; use the path only as a last resort. The user does not copy or paste
   output. On failure, diagnose from the log's `!ERROR:` lines and
   prefix (`[NETWORK]`, `[CASCADE-REST-CMS]`, or none for a Cascade
   error, including a non-200 status such as `501 Not Implemented`),
   fix the script, validate again, and ask the user to run it again.
f. For destructive operations on EXISTING assets (`delete`, `publish`,
   overwrite), the stage before the write is a read-only preview that
   calls `script_log.note()` once per affected asset (type and id
   first, path only if needed). You read the `[NOTE]` lines from the
   log and the user confirms that list. No preview is needed for an
   asset an earlier stage created, but its identifier must come from
   that stage's `[RESULT]` line, verbatim. Write notes inside the
   `with` block. Callbacks in a process pool cannot call `note()`:
   they return values and the main script notes them. Never
   look an asset up by name to delete or overwrite it.
g. Assembly stage: when every write has passed on its own, run the
   complete script once on one item, and read its log.
h. Only then deliver the full script (Step 7) and say which stages
   passed.

**Step 7 — Present** the script with a one-line note on what it does and which
environment variables it needs. If the script has runtime-dynamic values the
validator cannot check statically (CSV rows, search results), say so rather
than implying full coverage.

### Checklist

```
[ ] Asked the user how env vars/config are supplied (Step 1)
[ ] Template chosen from templates/INDEX.md
[ ] Field names/aliases confirmed in references/operations_schema.json
[ ] Only CascadeWrapperBase used — no driver, no event loop, no ClientSession
[ ] Asset writes use attribute assignment, not asset["x"] = ...
[ ] Path built as Path(site_name=..., asset_type=...), not a dict
[ ] No try/except or isinstance() around submit_requests()
[ ] Results read from .success / .failed, not isinstance checks
[ ] Every param, return and module-level var is type-hinted
[ ] ruff format --line-length 60 --isolated run on the file
[ ] No line longer than 60 characters (code, comments, docstrings)
[ ] validate_script.py exits 0
[ ] Scripts with writes: delivered one write at a time, each stage's log read by you (Step 6)
```

## What the library actually does

**Queue, then submit.** `cascade.operations.<op>(...)` queues a request.
Nothing hits the network until `cascade.submit_requests()`, which runs the whole
batch concurrently and then clears the queue. One `submit_requests()` per batch.

**Results come back in creation order.** `submit_requests()` returns one
entry per queued chain, in the order the chains were created (one per
identifier for `read`, `delete`, `publish` and other identifier-addressed
operations), so zipping the full `results` list against your inputs
is safe. Do not zip against `.success`: it leaves out failed chains, so
the pairs shift. A list `create` or `edit` is the exception: it is
one chain. Failures are included in the list, never dropped.

**The context manager owns failure handling.** Do not wrap
`submit_requests()` in `try/except` and do not write `isinstance()` checks.
`submit_requests()` returns a `ChainResults` — a `list` subclass with two
extra properties:

- `.success` — results from chains that did not fail (typed from the
  `result_type` you pass, so `submit_requests(Asset).success` is `list[Asset]`).
- `.failed` — `ChainFailure` records (`identifier`, `step_name`,
  `category`, `message`, `error`) for chains that failed.

```python
results = cascade.submit_requests(Asset)
for asset in results.success:
    print(asset.get("path"))
```

Raw values (`CascadeError`, `Exception`) stay in the list itself if you
index or iterate it directly, but scripts should use `.success` / `.failed`.

**Exit behavior.** At `with` exit the wrapper prints a tally
(`"N failed, M succeeded"`, plus `": reference log for details"` when the
API, network or library failed) and, by default
(`exit_on_failure=True`), exits non-zero when anything failed.
Pass `exit_on_failure=False` only when
embedding (the MCP server does); then read `.success` / `.failed` yourself.
Failure categories, shown as a prefix on the `!ERROR:` line in the
logfile: `[NETWORK]` (connection/timeout), `[CASCADE-REST-CMS]` (library
or parse error at an operation step), no prefix for API rejections and
for exceptions raised in your callbacks.

**Console output and logs.** Status lines (`[INIT]`, `[LOG]`, `[DONE]`,
the tally, `[EXIT]`) go to **stderr**, not stdout. At startup the
script prints `[LOG]: <path>` to stderr, the path of this run's log
file (default directory `./logs/`; `log_dir=` changes it). The log
file records the tally and a final `[EXIT-CODE]: <outcome>` line, so an
agent can judge a run from the log alone.

**`[RESULT]` and `[NOTE]` lines.** After a chain's pipeline line the
library writes one `[RESULT]` line per successful write (never for
reads or failures): `[RESULT]: create <type> <id> [<path>]`, or
`[RESULT]: <operation> [<type> <id> <path>] succeeded`. `<id>` is
32 hex characters and `<path>` starts with `/`. A script adds its
own `[NOTE]: <text>` lines, inside the `with` block:

```python
from cascade_cms.utils import script_log

script_log.note("will delete page <id>")
```

Outside a run a note is dropped with a `RuntimeWarning`.

**Non-200 responses are Cascade failures.** Cascade answers HTTP 200
with a JSON body, so any other status came from the web server layer.
It becomes a failure with no prefix whose message is the status and
reason (for example `501 Not Implemented`); the HTML body is never
logged. There is no response cache.

**Code after the `with` block is success-only.** It runs only when the
run had no failures, so put success-only output there. Anything that
must run every time goes inside the block.

**A failed batch does not stop the block.** The wrapper acts only at
`with` exit, so later `submit_requests()` calls in the same block
still run. When a batch depends on an earlier one, stop first:

```python
first = cascade.submit_requests(Asset)
if first.failed:
    return  # wrapper still prints the tally, exits 1
```

**A batch that breaks raises `CascadeBatchError`** (chained to the
original exception) instead of returning `[]`; with the default
`exit_on_failure=True` the wrapper logs it and exits 1 without a
traceback. Import it from `cascade_cms.failures` only if you need it.
`ChainResults`, `ChainFailure` and `CascadeBatchError` also live there;
they are not exported from `cascade_cms`.

**No output files by default.** Never write an output file (CSV,
JSON, text) unless the user explicitly asks for one and gives the
path. Print reports to stdout; the user can redirect them. The
library's own `./logs/` is the only file a script creates by
default.

**Write operations return `CascadeSuccess`.** `edit`, `delete`, `copy`, `move`,
`publish`, `checkIn`, `siteCopy`, `performWorkflowTransition`,
`editAccessRights`, `editWorkflowSettings`, `editPreference`, `markMessage`,
`deleteMessage` all return `CascadeSuccess` (`{"success": true}`) on success and
`CascadeError` on failure. `checkOut` is the exception — it returns
`CheckedOutAsset`. `read` returns `Asset`; `create` returns `IdentifierType`.
Both result types are strict (`cascade-cms-rest` 3.1.6+):
`CascadeSuccess.success` is `Literal[True]` and forbids extra keys,
`CascadeError.success` is `Literal[False]`. Use `.success` / `.failed` on the
`submit_requests()` result rather than checking types yourself.

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

**Models use snake_case field names (3.2.2+).** Write
`IdentifierType(identifier=..., asset_type=...)`,
`SearchInformation(site_name=..., search_terms=...)`,
`workflowTransitionInformation(workflow_identifier=..., ...)`. The
camelCase names still validate and are what go out on the wire, but
scripts use snake_case. Read results by attribute:
`checked_out.working_copy_identifier`, `step.label`,
`action.action_identifier`. `IdentifierType` forbids extra keys.

**`Path` is a model, not a dict (3.2.2+).** Build it as
`Path(site_name="www", path="about/index", asset_type="page")`; a
dict literal crashes in `resolve_identifier()`, and a `Path` without
`site_name` raises `ValueError("Path identifiers require site_name to
build the request URL")`. Read it by attribute (`p.site_name`).

**Callbacks** registered with `.then(fn)` or `.then([fn, ...])` run per result
after the batch: sequential per result, concurrent across results. Async
callbacks are awaited; sync callbacks run in an executor (`ThreadPoolExecutor`
by default — pass a `ProcessPoolExecutor` via `submit_requests(executor=...)`
for CPU-bound work). **A callback that raises stops that chain**; the other
chains finish, then the first callback exception is raised, unwrapped,
at `with` exit (exit code 1, no library prefix). Catch errors inside
the callback if you want tolerant processing.

**A callback's return value is the next input.** Returning `None`
passes the previous result through unchanged, so a payload-building
callback that forgets `return` hands on the original `Asset`. When a
chain ends in a callback, `.success` holds what it returned; pass that type
to `submit_requests()` (e.g. `submit_requests(NewAsset)`).

**Chained `create()`, `edit()` and `delete()` take a callable**
(3.2.2+). It is called with the previous node's result when the
chain runs, so read → build → create → delete is ONE chain and one
`submit_requests()`:

```python
def to_new(page: Asset) -> NewAsset: ...
def same(new_id: IdentifierType) -> IdentifierType:
    return new_id  # delete exactly what create made

cascade.operations.read(src).create(to_new).delete(same)
```

`create(fn)` must return a `NewAsset` (or a list); `delete(fn)` an
identifier (or a list). A callable returning a list is one
multi-item node: every item's result is kept, and per-item errors do
not stop the chain (see the list note below). The callable form works
only as a chained step; the first operation in a chain
(`cascade.operations.create(...)`) needs a concrete value.

**After a list `create` or `edit`,** a following callback receives a
list that may contain `CascadeError` items. The chain does not stop on
per-item errors, so check each item before using it. (The chain is
still recorded once in `.failed` and left out of `.success`.) To get one
chain, and one `.success` / `.failed` entry, per asset, queue one
`create()` / `edit()` per asset instead of passing a list.

Shared state touched from a sync callback needs a
`threading.Lock`.

## Script conventions

```python
#!/usr/bin/env python3
"""One-line description."""

import os

from cascade_cms.cmstypes import Asset
from cascade_cms.wrapper import (
    CascadeWrapperBase,
    EnvironmentVars,
)

# ----- Configuration -----
environment_variables: EnvironmentVars = {
    "API_KEY": os.environ["CASCADE_API_KEY"],
    "CASCADE_URL": os.environ["CASCADE_URL"],
    "SERVER": os.environ.get("SERVER", "default"),
}


def report(result: Asset) -> None:
    print(result.get("path"))


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        cascade.operations.read(...).then(report)
        cascade.submit_requests(Asset)


if __name__ == "__main__":
    main()
```

**Type hints are mandatory.** Every function and method parameter, every
return type (`-> None` when nothing is returned), every callback, nested
function and module-level variable carries an annotation. The config block
is `EnvironmentVars` (from `cascade_cms.wrapper`), targets are
`list[IdentifierType]`, and a `.then()` callback taking a read result is
`Asset` (a read result is never a `CascadeError` inside a callback).
Only `self`/`cls` and lambdas are exempt.
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
`RequestExecutor`), never touch the event loop
(`new_event_loop`, `set_event_loop`, `run_until_complete`, `get_event_loop`),
never construct an `aiohttp.ClientSession`. The wrapper owns the loop and
session for the life of the `with` block and wires them into logging and
callback execution — bypassing it produces unclosed sessions, unlogged
requests, and an uncleared request queue.

Other conventions:

- **Config block, not a .env framework.** Show `API_KEY` / `CASCADE_URL` /
  `SERVER` as one block, filled the way the user chose at Step 1. Do not
  assume `python-dotenv` or any particular mechanism.
- **No try/except around `submit_requests()`.** The context manager
  logs failures, prints the tally and sets the exit code.
- **Normal logging by default** — pass no `debug` argument unless the user asks
  for verbose output. Debug mode needs a fully specified config dict (every key,
  no inferred defaults); see `environment_and_config.debug_config` in the schema.
- **Comments explain why, not what.** Don't write `# read the asset` above a
  `read()` call. Do explain a UUID-vs-Path choice, a required alias, or why a
  callback runs in a process pool.
- **One `main()`**, guarded by `if __name__ == "__main__":`.
- **Nothing platform-specific.** The script must run in a bare `python3`
  interpreter (3.12+). Dependencies are
  `cascade_cms` plus stdlib.

## Examples

### Staged writes: read, create, delete

The user asks for a script that reads an asset, creates a copy from its
data, then deletes the copy.

- **Stage 1: read + create**, on one item. The library logs
  `[RESULT]: create page <id> <path>` by itself. The agent gives the
  run command and says stage 1 leaves a copy behind. After the user
  says it ran, the agent reads the log file named on the `[LOG]:`
  line and checks 0 failed, `[EXIT-CODE]: 0` and the `[RESULT]` id.
- **Stage 2: delete only.** The script calls
  `script_log.note(f"will delete page {new_id}")`, then deletes the
  id from stage 1's `[RESULT]` line, copied verbatim. It does NOT
  re-run the create. The agent reads the log again: a
  `[RESULT]: delete page <id> succeeded` line, 0 failed.
- **Stage 3: assembly.** The full read → create → delete chain runs
  once on one item, and the agent reads its log. Only then is the full
  script delivered, with the stages that passed.

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
    environment_variables
) as cascade:
    # One create() per payload gives one chain per asset.
    for payload in payloads:
        cascade.operations.create(payload)
    results = cascade.submit_requests(IdentifierType)

    for result in results.success:
        kind, new_id = result.get_type, result.get_id
        print(f"Created {kind} {new_id}")
```

### Read, modify, save

```python
with CascadeWrapperBase(
    environment_variables
) as cascade:
    cascade.operations.read(targets)
    editable: list[Asset] = cascade.submit_requests(
        Asset
    ).success
    for asset in editable:
        # Attribute assignment, never asset[...] = ...
        asset.displayName = "Annual Report 2025"
        keywords: str = asset.get("keywords") or ""
        asset.keywords = keywords.strip().lower()
        # One edit() per asset: one chain each.
        cascade.operations.edit(asset)

    # A write operation resolves to CascadeSuccess.
    cascade.submit_requests(CascadeSuccess)
```

### Workflow transition

```python
with CascadeWrapperBase(
    environment_variables
) as cascade:
    cascade.operations.readWorkflowInformation(target)
    infos = cascade.submit_requests(workflowInformation)

    for info in infos.success:
        for step in info.ordered_steps:
            if step.label != info.current_step:
                continue
            for action in step.actions:
                if action["action_identifier"] != "approve":
                    continue
                transition = workflowTransitionInformation(
                    workflow_identifier=info.workflow_info_id,
                    action_identifier="approve",
                    transition_comment="Advanced.",
                )
                ops = cascade.operations
                ops.performWorkflowTransition(
                    target, transition
                )

    cascade.submit_requests(CascadeSuccess)
```

## Reference files

Read these on demand — don't load them all up front.

| File | Read it when |
|---|---|
| `templates/INDEX.md` | Always, at Step 2 — pick a starting template |
| `templates/*.py` | 19 runnable, validator-passing scripts |
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
`cascade-cms-rest` package (currently 3.3.0), so the validator can do real
Pydantic instantiation instead of schema lookups. A stale snapshot silently
rejects correct scripts, so never copy files by hand. From the repo root, in
the `.conda` environment:

```bash
./.conda/bin/pip install --upgrade cascade-cms-rest
./.conda/bin/python build_release.py            # sync, validate, zip
./.conda/bin/python build_release.py --no-zip   # sync + validate only
```

The build re-syncs the snapshot, rewrites `cascade_cms/_bundle_manifest.json`
(version + per-file sha256), validates all 19 templates, and **aborts if any
fails**. `validate_script.py` prints the bundled version on every run and warns
when the snapshot no longer matches its manifest.

If validation fails with `ModuleNotFoundError` for a library dependency:

```bash
pip install pydantic aiohttp typing_extensions
```

Install `ruff` (`pip install ruff`) and run `ruff format --line-length 60
--isolated <file>` before validating; with it installed the validator also
runs `ruff format --check --line-length 60`.

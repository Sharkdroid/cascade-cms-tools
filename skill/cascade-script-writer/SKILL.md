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

**Step 0 — Open the session log.** On every invocation of this skill,
before any other work:

a. Create `reports/` under the user's working directory if it does not
   exist.
b. Create a new file `reports/cascade-script-{YYYYMMDD-HHMMSS}.txt`,
   using the local time at session open. If two sessions open in the
   same second, add a counter suffix (`-1`, `-2`). Never overwrite or
   truncate an existing log. UTF-8, no BOM.
c. Copy the structure of `references/SESSION_LOG_TEMPLATE.txt` and fill
   the header (Skill version, Session opened, Working dir, Task, the
   task quoted verbatim). Never edit the template itself.
d. Leave the other sections open. Append each one as its step
   completes, never only at the end, so a session that stops midway
   leaves a partial log showing how far it got.
e. Suggest the user add `reports/` to their `.gitignore` if they use
   git. The skill does not edit it.
f. The log is written only when this skill is invoked.

This log is your own working record. It is not the runtime log
the library writes, `script_log.note()` lines in scripts, or the
`REPORT_TEMPLATE.md` retrospective; none of those change.

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

Append TASK BREAKDOWN to the session log.

**Step 2 — Pick a template.** Read `templates/INDEX.md` and choose the row
matching the task shape. Only name a template that
`python scripts/new_script.py --list` prints; never cite or invent a name from
memory. Do not write a script from scratch — the templates
all pass the validator as written, so starting from one means only your
task-specific edits can break it.

```bash
python scripts/new_script.py --template create-bulk --out my_script.py
```

If no template fits, start from the closest one and replace the operation.

Append TEMPLATE SELECTED to the log (template, reason, gaps).

**Step 3 — Look up exact names.** Read `references/operations_schema.json` for
method signatures, payload fields, and aliases. Cascade payloads use aliases
(`parentFolderId` vs `parent_folder_id`) that must match exactly — never guess
a field name. For `Asset` reads/writes, read `references/asset_api.md`. When
the schema is not detailed enough, read the bundled source in `cascade_cms/`;
it is ground truth.

Append each file you open to REFERENCES READ as you open it. After
each MCP tool call, append an MCP TOOL CALLS block: tool name, key
inputs, one sentence on what it returned.

**Then confirm, live, where every written field goes.** The bundled source
is ground truth for the *library*. Live Cascade data is ground truth for
the *asset*. Before a script writes any field, whether through an `edit`
callable, `edit(asset)`, a `NewAsset(...)` keyword, or a structured-data
node, confirm the field's resolved path on real data with the Cascade MCP
server. Never place a field by its name, a template, these docs or memory.
Cascade silently ignores fields it does not recognise: the write reports
success and nothing changes. A misplaced or invented field is a ghost field
that no log, validator or result type will catch.

- **Edit:** run `cascade_query_asset(target, 'find("<field>")')` on one of
  the script's actual targets.
- **Create:** use `cascade_search` to find an existing asset of the same
  type in the target site, from the same folder or content type if
  possible. Then run `find("<field>")` on it.
- **Structured data:** use `cascade_get_data_structure` (see "Editing
  structured-data nodes").
- **Page configurations are READ-ONLY.** A script cannot write them
  through a page (Cascade drops the edit), so there is no path to confirm.
  Edit regions on the `template` asset (`pageRegions`) and
  configurations on the `pageConfigurationSet` asset
  (`pageConfiguration`). `cascade_get_page_config` is for reading only.

Write the field at exactly the path returned:

| Resolved path | In an edit callable | In `NewAsset(...)` |
|---|---|---|
| `$.name` | `asset.name = ...` | `name=...` |
| `$.metadata.title` | `asset.get("metadata")["title"] = ...` | `metadata={"title": ...}` |

- No match means the field does not exist on that asset. Do not write it;
  ask the user.
- Matches at more than one path: ask which one is meant.
- Read shapes and paths only (`format="concise"`), never content you do not
  need.
- List each written field with its verified path when you present the
  script (Step 7).

**Definition-owned fields.** Some fields belong to another asset's
definition, and a page cannot change them (live-verified):

- Page configurations and regions are read-only on a page.
- A dynamic metadata field's `name` (`metadata.dynamicFields[]`) is
  defined by the metadata set and cannot be changed through the page.
  Edit its `fieldValues` only. Renaming or adding a field is a change to
  the metadata set asset. Each entry is `{"name": <str>, "fieldValues":
  [{"value": <str>}, ...]}` (live-verified); there is no `value` key on
  the entry itself. Edit `fieldValues` through the live dict, like other
  metadata:

```python
metadata = asset.get("metadata")
for field in metadata.get("dynamicFields") or []:
    if field.get("name") == "audience":
        field["fieldValues"] = [{"value": "students"}]
```

- A page's structured data follows its data definition (Keith, tested
  live). Cascade reconciles the page against that schema: a node the
  schema does not have is ignored, and a removed node takes the field's
  `default` where one exists. A value that is not a valid choice is
  still stored (see the radio-button rule under "What the library
  actually does"). So a page edit changes values and the instances of
repeatable (`multiple`) groups, never the nodes themselves. A node
cannot be moved to another group, renamed (its `identifier`), removed or
created on a page; all of that goes through the definition asset. The
same holds for page configurations and regions (source: the template
and `pageConfigurationSet`) and dynamic metadata fields (source: the
metadata set): a page carries their values, and moving, renaming,
adding or removing one is a change to the source asset.
Adding and removing instances of a repeatable group is used in
production (a script that replaces the whole set of instances); we have
not live-tested it ourselves.

Schema structure is edited at its source, never on the page. Adding, removing,
moving or renaming a field, group, radio item or default is a change to
the data definition; regions and configurations belong to the template
and `pageConfigurationSet`; a dynamic metadata field belongs to the
metadata set. Moving, renaming, adding or deleting a node on a page is
not a fix: Cascade drops or resets it. When a task needs a structural change, say which
source asset owns it and plan the script against that asset. A data
definition is shared by every page whose content type uses it, so state
the blast radius, use a DEV asset first, and read the definition back
afterwards.

Changing a source does not update the pages that use it (Keith, live).
After a structural change to a data definition, page configuration set
or metadata set, an existing page keeps its old stored data: the editor
can show the new default while a REST read still returns the previous
value, and the page renders correctly only after it is saved again (a
UI save, or `edit()` on the page). Plan a separate, reviewed stage that
re-saves each affected page, then confirm one in the Cascade UI.

After the first write stage (Step 6e), read the written fields back with
`cascade_query_asset` and confirm the new values are there. A success
result does not prove the field landed. The MCP is read-only; this never
writes.

Without the MCP connected, say so. Ask the user for one real asset's keys
and paths (values redacted), or add a read-only first stage that notes the
resolved paths. Mark every written field UNVERIFIED in Step 7 until one of
those confirms it.

**Step 4 — Edit the script** for the specific task. Keep the template's
structure: config block, `main()`, `with CascadeWrapperBase(...)`, one
`submit_requests()` per batch. Keep every function, parameter and module-level
variable **type-hinted** and every line **60 characters or fewer** — see
"Script conventions" below. Templates already comply; your edits must too.

Append a DESIGN DECISIONS block for each judgment call (ambiguity,
choosing between valid approaches, a template gap worked around).

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

Append a VALIDATION RUNS block after every run, pass or fail.

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
   fix the script, validate again, and ask the user to run it again. A
   guard of the script's own that fails inside an edit callable is logged
   with the `[CASCADE-REST-CMS]` prefix (category LIBRARY); read the
   message after `ValueError:`.
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

Append a STAGED WRITES block after each stage (plan, expected output,
the exit code and tally the user reported, decision; diagnosis if
unexpected).

**Step 7 — Present** the script with a one-line note on what it does and which
environment variables it needs. For scripts that write, list each written
field with its live-verified path, or mark it UNVERIFIED (Step 3). If the script has runtime-dynamic values the
validator cannot check statically (CSV rows, search results), say so rather
than implying full coverage.

Append DELIVERED to the session log and close it.

### Checklist

```
[ ] Session log opened in reports/ and appended step by step (Step 0)
[ ] Asked the user how env vars/config are supplied (Step 1)
[ ] Template chosen from templates/INDEX.md
[ ] Field names/aliases confirmed in references/operations_schema.json
[ ] Every field an edit/create writes placed at its live-resolved path
    (MCP find(); UNVERIFIED if no MCP); no ghost fields (Step 3)
[ ] First write stage read back via the MCP to confirm the value landed
[ ] Schema checked for gate radio buttons (show-fields) and required
    siblings of each written field; user told to check the rendered page
[ ] Only CascadeWrapperBase used — no driver, no event loop, no ClientSession
[ ] Asset writes use attribute assignment, not asset["x"] = ...
[ ] Path built as Path(site_name=..., asset_type=...), not a dict
[ ] No try/except or isinstance() around submit_requests()
[ ] Results read from .success / .failed, not isinstance checks
[ ] Every param, return and module-level var is type-hinted
[ ] ruff format --line-length 60 --isolated run on the file
[ ] No line longer than 60 characters (code, comments, docstrings)
[ ] validate_script.py exits 0
[ ] No submit_requests() inside a loop, recursion or per-item helper
    (unless marked "# barrier:" for a level-by-level fetch)
[ ] Independent reads queued in the same batch; submits == dependency depth
[ ] References resolved level by level from a memo dict
[ ] Read-then-write on the same asset is one chain, read(x).edit(fn)
    (exception: edit-held-assets)
[ ] Template names come from new_script.py --list, never from memory
[ ] Structured-data edits name a group AND a field, guard None and the
    match count, and never touch structuredData as a whole
[ ] Scripts with writes: delivered one write at a time, each stage's log read by you (Step 6)
```

## What the library actually does

**Queue, then submit.** `cascade.operations.<op>(...)` queues a request.
Nothing hits the network until `cascade.submit_requests()`, which runs the whole
batch concurrently and then clears the queue. One `submit_requests()` per batch.

### Barrier rules

Every `submit_requests()` is a barrier; batch to the level, not the item.
Chains inside one submit run concurrently (up to 50 in flight); two submits
never overlap. Waiting time is roughly (number of submits) x (slowest
request per submit), so minimise submits, not requests.

1. Never call `submit_requests()` inside a loop, a recursive function, a
   parser, or a per-item helper. Collect identifiers first, queue one
   `read([...])`, submit once, then process from a dict. The one exception
   is a deliberate level loop (e.g. template `read-tree`), marked with
   `# barrier: <reason>` on the innermost loop's header line.
2. Independent reads share one submit. If B and C depend only on A, read A,
   then queue B and C together. Sequential submits are for a real data
   dependency only.
3. Discover, then fetch, then parse. Queue every unseen identifier at the
   current level, submit once, inspect results for the next level. Keep
   parsing free of I/O.
4. Memoise by identifier. The library has no request cache. Keep a dict of
   what was fetched; never queue an identifier twice.
5. Do not hide a submit inside a helper. If a helper submits, put "submit"
   in its name and call it only from top-level orchestration.
6. List-driven scripts run in phases, not per item: validate/build
   everything first, read everything in one submit, transform in memory,
   write everything in one submit.
7. Chain a dependent write instead of submitting twice. When a write only
   needs the previous read's result, use `read(x).edit(fn)` or
   `read(x).create(fn)`.
8. Do not catch `CascadeBatchError` per item. A broken batch should stop
   the run.

The validator warns on a submit inside a loop or recursion. It cannot
enforce "keep the held-asset gap short"; that rule is guidance.

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
asset.get("name")            # read
asset.name = "new-name"      # write
asset["name"] = "new-name"   # TypeError: no __setitem__
```

`Asset.__setattr__` also rejects a type change on an existing field
(`str` → `int` raises). Details in `references/asset_api.md`.

Attribute assignment only reaches **top-level** fields. Nested fields such
as `metadata` (where `displayName`, `title`, `summary`, `teaser` and
`keywords` live) are edited through the live reference —
`asset.displayName = ...` would add a stray top-level key, which Cascade
silently ignores — the edit reports success and `metadata.displayName` is
unchanged:

```python
metadata = asset.get("metadata")          # live dict
metadata["displayName"] = "Annual Report"
keywords = metadata.get("keywords") or ""  # dict.get: no KeyError
```

**`Asset.get()` takes dotted paths (3.1.6+).** `asset.get("a.b.c")` walks
nested dicts (max depth 5; deeper raises `ValueError`) and raises `KeyError`
when any segment is missing — there is no default argument, so guard with
`try/except KeyError` when a field may be absent. Use it for nested metadata
(`asset.get("metadata.dynamicFields")`), **not** for `structuredData` or
`pageConfigurations`: `get()` emits a warning for those roots. Use
`asset.get_data_structure(group, identifier, direct=True)` and
`asset.get_page_configuration(name, region)` instead. Structured-data nodes
are live references you can edit in place; page configurations and regions
are READ-ONLY snapshots (3.7.0+) — Cascade ignores region edits on `edit()`,
so edit the `template` asset's `pageRegions` (or the `pageConfigurationSet`
asset) instead. `noBlock`/`noFormat` are override
checkboxes, independent of assignment: check
`block_id`/`block_path`/`format_id`/`format_path` for "has a block or
format", and match regions by `name` (their order changes on save). Assigning `structuredData` is a
validator ERROR, and reading `._data["structuredData"]` is a warning.

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

### Create vs edit

- `create(payload)` needs no earlier step. It takes a `NewAsset`, which is
  validated when you construct it. Build every `NewAsset` before opening the
  wrapper. One `create()` per payload gives one chain each.
- `edit` needs an existing `Asset`, which comes from a read. Preferred:
  `read(x).edit(fn)`. One chain, one submit, fresh data. `edit` takes
  `(payload, parser=...)`, so `read(x).edit(identifier, fn)` is wrong.
- Exception: assets you read EARLIER in the same script may be edited LATER
  with `edit(asset)`, one `edit()` call per asset (template
  `edit-held-assets`). The held `Asset` is a snapshot and the edit
  overwrites whatever changed in Cascade meanwhile. Keep the gap short and
  re-read if anything in between could change those assets.
- If a create needs data from Cascade (for example a data definition),
  fetch it in an earlier phase (template `read-graph`), then build the
  `NewAsset`.

**After a list `create` or `edit`,** a following callback receives a
list that may contain `CascadeError` items. The chain does not stop on
per-item errors, so check each item before using it. (The chain is
still recorded once in `.failed` and left out of `.success`.) To get one
chain, and one `.success` / `.failed` entry, per asset, queue one
`create()` / `edit()` per asset instead of passing a list.

Shared state touched from a sync callback needs a
`threading.Lock`.

### to_identifiers

```python
from cascade_cms.utils import to_identifiers
```

`to_identifiers(asset.get("children"))` turns a folder's raw children
entries into `IdentifierType` objects (recycled entries dropped unless
`include_recycled=True`). It raises `ValueError`, naming the entry index,
for a malformed entry. Use it instead of `IdentifierType(**child)`.
`asset.get()` has no default, so guard a possibly missing key with
`try/except KeyError`.

### Editing structured-data nodes

Address the smallest thing: one group, one field.

```python
nodes = asset.get_data_structure(
    "contact", "phone", direct=True
)
```

It returns live references to the matching nodes, so setting a node's
value edits the asset in place. Return the Asset from the callback.
Template: `callback-structured-data-edit`.

Do not fetch, print, return or replace `structuredData` as a whole:
`asset.get("structuredData")`, `asset.structuredData = ...` and
`asset._data["structuredData"]`. The library warns on the first and does
not block the others. The validator fails the second and warns on the
third.

Names come from live data, not guesses. If the Cascade MCP server is
connected, confirm group and field identifiers with
`cascade_get_data_structure` before writing them into a script.
Otherwise ask the user. `get_data_structure()` only sees nodes present in
the asset it is called on, so it cannot tell a typo from an absent field.

Guard the result. `get_data_structure()` returns `None` for any miss
(typo, absent group, no structured data). A callback that then returns
the unchanged asset makes the edit succeed with nothing changed. Raise
inside the callback when the result is empty, and compare the count with
what you expect: a group identifier can repeat and nest, and every group
with that identifier is matched, nested ones included. The count cannot
catch a nested group's same-named field (see "Repeated and nested
groups"). If the count differs, stop and ask.

Change only what you have confirmed. Confirm the node's live shape first
(MCP, or a read-only preview stage). Text fields and radio buttons
(live-verified) keep their value in `node["text"]`. Multi-select,
checkbox, datetime and calendar nodes are also plain `type: "text"`
nodes with a special string in `text`; see "Special text nodes" below.
A node type not listed there is unverified: confirm its live shape before
writing, never guess the encoding, and change only the fields you
verified.

**Special text nodes.** Cascade type-checks none of these, so a wrong
string is stored and then breaks the editor. The schema, not the node,
tells you the type: `cascade_get_data_structure` with `node_identifier`.
Never type these strings by hand: start from
`callback-structured-data-edit`, set `FIELD_KIND` (and
`ALLOWED_OPTIONS` from the schema), and let its encoder build the value.
It raises on an unlisted option, a str where a date belongs, or a naive
datetime.

- Multi-select (live-verified): ONE node, `text` is each chosen option
  prefixed by `::CONTENT-XML-SELECTOR::`, e.g.
  `::CONTENT-XML-SELECTOR::One::CONTENT-XML-SELECTOR::Two`. The bare
  marker is the empty and default value; removing it just reverts to
  it. An option not in the schema's list stays in the stored string and
  the read still shows it, but the editor shows it deselected. Write
  only listed options.
- Checkbox (from a production script, not live-tested here): the same
  pattern with the marker `::CONTENT-XML-CHECKBOX::`, bare marker for
  empty. `""` does not clear it.
- Calendar: `MM-DD-YYYY` (Keith). Not validated: a malformed string
  such as a long run of digits is stored and displayed, and opening the
  date picker on it crashed the browser. Check the format in the script
  before writing.
- Datetime: the field value is Unix epoch MILLISECONDS (Keith), not an
  ISO string. Do not mix it up with asset dates such as
  `lastModifiedDate`, `lastPublishedDate` and `createdDate`, which are
  ISO 8601 UTC with milliseconds and a `Z`. Two formats, two places:
  asset date fields are ISO; a `datetime` structured-data node is epoch
  ms.
- To clear a calendar or datetime field, remove the node's `text` key
  (Keith). The node stays; only the content goes.

File choosers (`type: "asset"`, live-verified on a file chooser):

- Shape: `{type, identifier, assetType, recycled}` when empty. A filled
  one adds `<kind>Id` and `<kind>Path` (`fileId`/`filePath`). For a
  multi-type chooser `assetType` stays the allowed list
  (`"page,file,symlink"`) and the keys take the chosen type
  (`symlinkId`/`symlinkPath`).
- Set: send `fileId`, `filePath` or both; Cascade stores both, resolved
  to the same asset. If the two name different assets, the id wins
  (Keith, tested). Send the id.
- Clear: delete the `<kind>Id`/`<kind>Path` keys. Setting them to
  `None` or `""` also ends with the keys absent, so use the delete.
- Untested: block and page choosers, chooser types other than file,
  and checkbox or multi-select. Confirm those live.

Repeated and nested groups (verified offline against a copy of a real
page's payload): `get_data_structure(group, field)` returns one node per
group INSTANCE across every parent, with no link back to the parent.
With the default search it takes the first depth-first match inside each
instance, which can be a nested group's node. When a field name also
exists in a child group (`title` in both), a lookup through the parent
can return the CHILD's node: the parent's own `title` if it comes first
in node order, the child's if a nested group comes first or if the
parent has no `title`. Rule: pass `direct=True`, which matches only the
group's own fields. When a group identifier repeats under different
parents, pass a tuple path ending at the group,
`("page-section", "column")`. A `str` is always ONE identifier (dots
allowed); a tuple is a path. Assert the count you expect, but the count
cannot catch this case: it is still 1 when the wrong node is returned.

Live data showed three details to respect:

- A node's `type` in the asset is `text` for radio buttons and other
  choosers too. The schema tells them apart: `cascade_get_data_structure`
  with `node_identifier` reports the field's `type` (null for free text,
  `radiobutton` and so on otherwise). Free-text fields (type null) are
  the safe default. Write a radio button only with a value taken from
  its `radio-item` list: Cascade stores any string you send (live-
  verified) and never rejects it. A stored value that is not a
  `radio-item` shows as `(empty)` in the editor while the read still
  returns it, and the rendered page can disagree with that read (live:
  stored `No`, item removed from the definition, image still shown).
  Only a look at the rendered page settles it.
- A text node with no value has no `text` key at all, so a script must not
  assume the key exists before it sets it.
- The instance can hold a group that the schema lookup does not list. If
  `cascade_get_data_structure` says a group is not found, check the
  instance with `cascade_query_asset` before deciding the name is wrong.

A successful write can change nothing the user sees. The REST API does
not enforce what the Cascade editor enforces: a `required` field can
be left blank, and a field's value is never checked against the rest of
the group. Live case: a script set the image chooser under `impact`
and the write persisted (a read-back showed `fileId`/`filePath`), yet
the page showed no image, because the sibling radio button
`display-impact` ("Display Impact Image?") was still `No` (its schema
default) and the page's format only renders the image when it is `Yes`.
The schema declares this link: `cascade_get_data_structure` with
`node_identifier` shows `required` and `default` on the field, and a
`radio-item` carrying `show-fields="<group/field>, ..."` names the
fields that choice reveals. Before you write a field:

- Read its group's schema (`cascade_get_data_structure(identifier,
  group)`, then each radio button with `node_identifier`). List any
  radio button whose `show-fields` names the field you write, and any
  `required` sibling.
- Set the gate to the value that shows the field, in the same edit, or
  tell the user it is left as is. Never leave a required field blank
  that the UI would have filled with its `default`.
- In Step 7, say the user must check the rendered page or preview in
  Cascade: a REST read-back proves the value is stored, not that it is
  displayed. A read-back cannot see a gate that is off.

A raise in the edit callable is logged as a LIBRARY failure
(`[CASCADE-REST-CMS]`) with your message after `ValueError:`. That prefix
does not mean the library is at fault.

Verify live, read-only. With the Cascade MCP server connected, check
names and shapes before you write them into a script:

- Do the group and field exist? Use
  `cascade_get_data_structure(identifier, group, node_identifier)`. It
  reads the SCHEMA (the bound data definition), and a wrong name gets you
  the valid ones. It reports the first matching group only, so it cannot
  show repeats or nesting.
- What does the live node look like, and how many will match? Use
  `cascade_query_asset(identifier, query, format="detailed")` with a
  narrow path: `find("structuredDataNodes")` locates the tree and a
  wildcard step lists one level at a time. Count matching nodes level by
  level. Read shapes, not whole trees.
- After a write stage, read the same node back with `cascade_query_asset`
  and compare. The MCP has no write tools.

Without the MCP, ask the user for the identifiers and the expected count,
and say the node shape is unverified (Step 3).

Stage the write (Step 6). The preview stage notes the asset id, the group
and field, and the match count, never the values. After the first write,
read the asset back to confirm the value.

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
        # Extra fields pass through at the path given.
        # title lives under metadata (confirmed live).
        metadata={"title": row["title"]},
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
        # metadata fields: edit via the live dict.
        metadata: dict = asset.get("metadata")
        metadata["displayName"] = "Annual Report 2025"
        keywords = str(metadata.get("keywords") or "")
        metadata["keywords"] = keywords.strip().lower()
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
| `references/SESSION_LOG_TEMPLATE.txt` | Always, at Step 0 — format of the session log |
| `templates/INDEX.md` | Always, at Step 2 — pick a starting template |
| `templates/*.py` | 22 runnable, validator-passing scripts |
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
`cascade-cms-rest` package (its version is recorded in
`cascade_cms/_bundle_manifest.json`), so the validator can do real
Pydantic instantiation instead of schema lookups. A stale snapshot silently
rejects correct scripts, so never copy files by hand. From the repo root, in
the `.conda` environment:

```bash
./.conda/bin/pip install --upgrade cascade-cms-rest
./.conda/bin/python build_release.py            # sync, validate, zip
./.conda/bin/python build_release.py --no-zip   # sync + validate only
```

The build re-syncs the snapshot, rewrites `cascade_cms/_bundle_manifest.json`
(version + per-file sha256), validates all 22 templates, and **aborts if any
fails**. `validate_script.py` prints the bundled version on every run and warns
when the snapshot no longer matches its manifest.

If validation fails with `ModuleNotFoundError` for a library dependency:

```bash
pip install pydantic aiohttp typing_extensions
```

Install `ruff` (`pip install ruff`) and run `ruff format --line-length 60
--isolated <file>` before validating; with it installed the validator also
runs `ruff format --check --line-length 60`.

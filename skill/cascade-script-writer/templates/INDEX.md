# Template index

Pick by **task shape**, copy, then edit. Every template here passes
`scripts/validate_script.py` as written — starting from one means you are
editing a known-good file instead of writing structure from memory.

```bash
python scripts/new_script.py --template create-bulk --out my_script.py
```

Every template is fully type-hinted and wraps at 60 characters. Your edits
must keep both: `validate_script.py` fails on a missing annotation or any
line over 60 characters.

## Core operations

Scripts with writes (`create-bulk`, `edit-in-place`, the workflow and
publish templates) are delivered in stages — see `SKILL.md` Step 6.

| Task shape | Template |
|---|---|
| Read specific assets by UUID and/or site+path | `read-identifiers` |
| Find assets by search, then read each one | `read-iterate` |
| Create many assets from a CSV or list | `create-bulk` |
| Read assets, change fields, save them back | `edit-in-place` |
| Read an asset's workflow and advance it | `workflow-orchestration` |
| Do the same work across several sites at once | `concurrent-multisite` |
| Simple task, results handled in a plain loop | `callback-none` |

## Callback patterns

| Task shape | Template |
|---|---|
| Run several transforms in order on each result | `callback-chain` |
| Handle mixed result types / tell success from failure | `callback-type-dispatch` |
| Feed results into a second, dependent batch | `callback-dependent` |
| Queue a follow-up publish based on what was read | `callback-conditional-publish` |
| Call an async API per result | `callback-async-io` |
| Combine a sync transform with an async hand-off | `callback-mixed-sync-async` |
| CPU-heavy per-asset work (parsing, hashing, images) | `callback-cpu-bound` |
| Count or collect across all results, print a report | `callback-accumulator` |
| Show progress while a long batch runs | `callback-progress-reporting` |
| Keep going when one result's processing fails | `callback-error-isolation` |
| Edit structured-data (data-definition) fields | `callback-structured-data-edit` |
| Inspect page-configuration regions | `callback-page-region-audit` |

## Failure handling

No template wraps `submit_requests()` in `try/except` or checks result
types. Read `.success` / `.failed` on the returned `ChainResults`; the
context manager prints a tally and exits non-zero on failure (code after
the `with` block does not run then). `callback-error-isolation` shows
tolerant per-item processing.

## Choosing a callback style

- **No callback** — sequential work over a small result list. Start here.
- **Sync callback** — blocking work (file I/O, `requests`, CPU). Runs in a
  `ThreadPoolExecutor` by default; pass a `ProcessPoolExecutor` for CPU-bound work.
- **Async callback** — the work is already awaitable. Awaited directly on the loop.

Shared state touched from a sync callback needs a `threading.Lock`: callbacks
run concurrently across results. A `ProcessPoolExecutor` does not share memory
at all, so accumulate in the parent instead.

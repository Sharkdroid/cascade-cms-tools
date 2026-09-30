# The `Asset` object

`Asset` is the result type of `read`. Unlike every other model in the library
it is **not** a Pydantic model — it is a thin wrapper around the raw
`{"asset": {"<type>": {...}}}` JSON, because Cascade's asset shape varies per
asset type. Nothing about its fields is schema-validated.

## Read and write

```python
asset.get("name")                 # read  — .get(), no default arg
asset.get("metadata.summary")     # read  — dotted path, depth <= 5
asset.name = "new-name"           # write — ATTRIBUTE assignment
asset.internal_type               # lowercase wrapper key: "page",
                                  # "file", "xhtmldatadefinitionblock", ...
```

`internal_type` is NOT the request-side literal. To build an
`IdentifierType`, use the type the script already knows, held in one
`AssetTypes` constant (the `TARGET_TYPE` pattern in the callback
templates); `IdentifierType(type=internal_type)` is rejected for blocks.

### `get()` semantics (cascade-cms-rest 3.1.6)

`get(key, max_depth=5)` splits `key` on `.` and walks nested dicts:

- **Missing key → `KeyError`.** There is no default argument, unlike
  `dict.get`. Wrap the read in `try/except KeyError` when the field may be
  absent, e.g. an optional metadata field.
- **Too deep → `ValueError`** when the path has more than `max_depth`
  segments.
- **Non-dict in the middle → `KeyError`** ("Cannot traverse into non-dict
  value").
- **`structuredData` / `pageConfigurations` roots emit a warning.** They
  still resolve, but the library steers you to `get_data_structure()` and
  `get_page_configuration()` below (structured-data nodes are editable live
  references; page configurations/regions are read-only snapshots).

```python
try:
    dynamic = asset.get("metadata.dynamicFields")
except KeyError:
    dynamic = []
```

**Optional keys are missing, not null.** A key Cascade has nothing for
is absent from the payload, e.g. `lastPublishedDate` on a page that was
never published. There is no `published` key on a page; use
`shouldBePublished` (bool) with `lastPublishedDate` and
`lastModifiedDate`. Read optional keys through a `KeyError` guard. Page
timestamps are ISO 8601 UTC with milliseconds and a `Z`
(`2025-01-31T14:02:11.000Z`): parse them with
`datetime.fromisoformat` before comparing, never compare the strings.

**Never `asset["displayName"] = value`.** `Asset` defines `__setattr__` and
`.get()`, and no `__setitem__` at all, so subscript assignment raises:

```python
asset["keywords"] = "x"
# TypeError: 'Asset' object does not support item assignment
```

Reading with `asset["keywords"]` fails the same way — there is no
`__getitem__` either. Use `.get()`.

Writes are single-level: `asset.name = ...` sets a top-level field.
Nested fields such as `metadata` are edited through the live reference:
`get()` the container and mutate it, or use the designated accessors.
`displayName`, `title`, `summary`, `teaser` and `keywords` live under
`metadata` — `asset.displayName = ...` adds a stray top-level key, which
Cascade silently ignores: the edit reports success and
`metadata.displayName` is unchanged:

```python
metadata = asset.get("metadata")               # live dict
metadata["displayName"] = "New Title"
keywords = metadata.get("keywords") or ""       # dict.get: no KeyError
```

**Definition-owned fields.** A page cannot change fields that another
asset's definition owns (live-verified):

- Page configurations and regions are read-only on a page.
- A dynamic metadata field's `name` (`metadata.dynamicFields[]`) is
  defined by the metadata set. Edit its `fieldValues` only; renaming or
  adding a field is a change to the metadata set asset. Each entry is
  `{"name": <str>, "fieldValues": [{"value": <str>}, ...]}`
  (live-verified); there is no `value` key on the entry itself:

```python
metadata = asset.get("metadata")               # live dict
for field in metadata.get("dynamicFields") or []:
    if field.get("name") == "audience":
        field["fieldValues"] = [{"value": "students"}]
```

## Type changes are rejected

`__setattr__` enforces that an existing field keeps its Python type:

```python
asset.name = "new-name"   # str -> str   OK
asset.name = 42           # str -> int   TypeError: Field 'name' has changed type
```

A field that is not already present is added without a type check. A field
whose current value is `None` has type `NoneType`, so assigning a `str` to it
raises — set it via the raw dict only if you know the server accepts it.

## Nothing is saved until you queue an edit

Mutating an `Asset` changes an in-memory object. To persist it:

```python
cascade.operations.edit(asset)          # one chain per asset
# Preferred: read(x).edit(fn). Exception: assets read EARLIER in
# the script may be edited later with edit(asset), one call per
# asset (template edit-held-assets); the held Asset is a snapshot.
# Folder children: cascade_cms.utils.to_identifiers(asset.get("children"))
# A list is ONE chain whose result is a list (see SKILL.md)
results = cascade.submit_requests(CascadeSuccess)
```

## Live references

Both accessors return **references into the asset**, so mutating what they
return mutates the asset itself:

```python
nodes = asset.get_data_structure("contact-block", "phone")
if nodes:
    for node in nodes:
        node["text"] = "+1 555 0100"    # asset is now modified

region = asset.get_page_configuration("ASPX", "FOOTER")
if region is not None:
    print(region.block_path, region.format_path)   # read-only
```

- `get_data_structure(group, identifier)` → `list[dict] | None`. Matches
  EVERY group with that identifier, nested ones included, and returns the
  matching node from each. Returns `None` on any miss (missing field or
  group, empty group, no structured data), so guard it: a typo otherwise
  edits nothing. A group node without `structuredDataNodes` raises
  `KeyError`. The returned nodes are live references, so edits reach the
  outgoing payload.
- `get_page_configuration(name)` → `PageConfiguration | None`.
- `get_page_configuration(name, region)` → `PageRegion | None`.

Both return `None` when nothing matches — always guard before using the result.

**Page configurations and regions are read-only (3.7.0+).** Any assignment
raises `ReadOnlyPageConfigError`; there is no `.content`. Cascade ignores
region edits sent with a page's `edit()`, so change regions on the `template`
asset (`pageRegions`) and configurations on the `pageConfigurationSet` asset
(`pageConfiguration`). **`noBlock`/`noFormat` are override checkboxes** (the UI's "no block" /
"no format"), independent of assignment: a region can have a
`blockId`/`blockPath` and `noBlock: true`, or `false` with no block. Read
"has a block/format" from `blockId`/`blockPath`/`formatId`/`formatPath`,
"override on" from the flag, and never infer one from the other. Region
order changes on save (and a region's `id` can change), so match regions
by `name`, never by index.

The library does not block `asset.structuredData = {...}` (a dict replaces a
dict silently). The validator does: it is an ERROR. Never assign, print or
return `structuredData` as a whole.

## Failed reads are reported by the wrapper

`read` yields a `CascadeError` value instead of an `Asset` when the
operation fails; it does not raise. `submit_requests()` returns a
`ChainResults` (a list) whose `.success` holds only successful results and
whose `.failed` holds `ChainFailure` records. A failed read never reaches
a `.then()` callback. No `isinstance` check is needed:

```python
for asset in cascade.submit_requests(Asset).success:
    print(asset.get("path"))
```

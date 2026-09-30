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

**A stored value is not a shown value.** REST does not enforce the
editor's required fields or show/hide rules. A structured-data field can
persist and still not render because a sibling radio button (its
`radio-item` has `show-fields` naming the field; `required`/`default`
appear on the field's schema node) is at its default. Live case: image
chooser set, `display-impact` still `No`, no image shown. See SKILL.md,
"What the library actually does" ("A successful write can change
nothing the user sees").

**Structure lives in the source (Keith, tested live).** Cascade
reconciles a page's structured data against its data definition: nodes
the schema lacks are ignored, removed nodes take the field default where
there is one, and a value that is not a valid choice is still stored.
A page edit changes values and repeatable-group instances, not the
nodes: moving a node to another group, renaming its identifier, and
removing or creating a node all go through the definition asset. The
same applies to page configurations/regions (template,
pageConfigurationSet) and dynamic metadata fields (metadata set). Add, remove,
move or rename fields, groups, radio items and defaults on the data
definition; regions/configurations on the template or
pageConfigurationSet; dynamic fields on the metadata set. A source
change does not update existing pages: each keeps its stored data (a REST
read can differ from the editor) until it is saved again, by the UI or
`edit()`.

**Special text nodes.** Multi-select is one text node,
`::CONTENT-XML-SELECTOR::` before each chosen option; bare marker =
empty/default; an unlisted option stays stored but the editor shows it
deselected. Checkbox follows the same pattern with
`::CONTENT-XML-CHECKBOX::` (production script; not live-tested here).
Calendar is `MM-DD-YYYY`, unvalidated (a garbage string crashed the date
picker). A `datetime` node is epoch MILLISECONDS; asset dates
(`lastModifiedDate` etc.) are ISO 8601 UTC. Never mix the two.

**Chooser nodes.** Empty: `{type, identifier, assetType, recycled}`.
Filled: plus `<kind>Id`/`<kind>Path` (`fileId`/`filePath`; a multi-type
chooser keeps `assetType` as the allowed list and uses the chosen
type's prefix). Send one key and Cascade stores both; if a pair names
two assets, the id wins. Delete the keys to clear (`None`/`""` end up absent too).
Only file choosers are verified.

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

## Turning raw `{id, type, path}` dicts into identifiers

Folder `children`, search hits and similar raw entries are dicts, not
`IdentifierType`. Convert them with `cascade_cms.utils` (pure, no I/O;
see `templates/read-tree.py`):

```python
from cascade_cms.utils import to_identifier, to_identifiers

ids = to_identifiers(asset.get("children"))  # drops recycled
one = to_identifier(entry)                   # never filters
```

- `to_identifiers(raw, include_recycled=False)` returns `[]` for `None`,
  drops entries with `recycled: true` unless `include_recycled=True`, and
  keeps order. `to_identifier` never filters by `recycled`.
- A malformed entry raises `ValueError` (never another type): the
  message names fields and reasons, never values, and the list form is
  prefixed `entry <index>: `. An unknown asset type is reported as
  "not a known asset type".
- A `path` value must be an object with `path` and `siteName`/`siteId`,
  not a string.
- Both accept Cascade's keys (`id`, `type`) and the snake_case names
  (`identifier`, `asset_type`).

## Live references

Both accessors return **references into the asset**, so mutating what they
return mutates the asset itself:

```python
nodes = asset.get_data_structure(
    "contact-block", "phone", direct=True
)
if nodes:
    for node in nodes:
        node["text"] = "+1 555 0100"    # asset is now modified

region = asset.get_page_configuration("ASPX", "FOOTER")
if region is not None:
    print(region.block_path, region.format_path)   # read-only
```

- `get_data_structure(group, identifier, *, direct=False)` →
  `list[dict] | None`. `group` is a `str` (ONE identifier; dots are part
  of it) or a `tuple[str, ...]` path that ends at the group, e.g.
  `("accordion", "row")`. Matches EVERY group with that identifier (or
  path), nested ones included, and returns the matching node from each.
  The default search is depth-first and can return a nested group's
  same-named field; pass `direct=True` to look only at the group's own
  fields, and a tuple path when the identifier repeats under different
  parents. Returns `None` on any miss (missing field or
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

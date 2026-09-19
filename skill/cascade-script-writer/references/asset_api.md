# The `Asset` object

`Asset` is the result type of `read`. Unlike every other model in the library
it is **not** a Pydantic model — it is a thin wrapper around the raw
`{"asset": {"<type>": {...}}}` JSON, because Cascade's asset shape varies per
asset type. Nothing about its fields is schema-validated.

## Read and write

```python
asset.get("displayName")          # read  — .get(), no default arg
asset.get("metadata.summary")     # read  — dotted path, depth <= 5
asset.displayName = "New Title"   # write — ATTRIBUTE assignment
asset.asset_type                  # "page", "file", "folder", ...
```

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
  `get_page_configuration()` below, which return editable live references.

```python
try:
    dynamic = asset.get("metadata.dynamicFields")
except KeyError:
    dynamic = []
```

**Never `asset["displayName"] = value`.** `Asset` defines `__setattr__` and
`.get()`, and no `__setitem__` at all, so subscript assignment raises:

```python
asset["keywords"] = "x"
# TypeError: 'Asset' object does not support item assignment
```

Reading with `asset["keywords"]` fails the same way — there is no
`__getitem__` either. Use `.get()`.

Writes are single-level: `asset.displayName = ...` sets a top-level field.
To change a nested value, `get()` the container (it is a live reference) and
mutate it, or use the designated accessors.

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
cascade.operations.edit(asset)          # or a list of assets
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
    region.content = "<p>updated</p>"   # asset is now modified
```

- `get_data_structure(group, identifier)` → `list[dict] | None`. Searches all
  instances of the named group, returning the first matching node per instance.
- `get_page_configuration(name)` → `PageConfiguration | None`.
- `get_page_configuration(name, region)` → `PageRegion | None`.

Both return `None` when nothing matches — always guard before using the result.

## Errors come back as values

`read` returns a `CascadeError` instead of an `Asset` when the operation
fails; it does not raise. Check before touching asset fields:

```python
for result in cascade.submit_requests(Asset):
    if isinstance(result, CascadeError):
        print(f"failed: {result.message}")
        continue
    print(result.get("path"))
```

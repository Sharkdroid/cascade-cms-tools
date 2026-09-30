#!/usr/bin/env python3
"""Read assets, modify fields on the returned Asset objects,
then save them.

Top-level fields are written by ATTRIBUTE (`asset.name =
...`), never by subscript. `Asset` defines `__setattr__`
and `.get()` but no `__setitem__`, so `asset["name"] =
...` raises TypeError. It also rejects a type change on an
existing field: if `name` is a str, assigning an int
raises TypeError.

Nested fields are edited through the live reference.
displayName, title, summary, teaser and keywords live
under `metadata`; `asset.displayName = ...` would add a
stray top-level key that Cascade silently ignores: the
edit succeeds and nothing changes. Read
optional keys with dict.get: `Asset.get` has no default
and raises KeyError on a missing key.

This is the preferred edit shape. One chain per target:
`read(identifier).edit(apply_edits)` reads the asset, then
`edit()`'s callable payload is invoked with that result to
produce the saved version. To edit assets you read EARLIER
in the script, see edit-held-assets.

TARGETS can come from anywhere (a list, JSON, a database,
an API, a search); it is only a placeholder here.

A chain that fails to read never reaches edit — its
chain is recorded in `results.failed` and is left out
of `results.success`.
"""

import os
import uuid

from cascade_cms.cmstypes import (
    Asset,
    CascadeSuccess,
    IdentifierType,
)
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

# Placeholder: any source of identifiers works.
TARGETS: list[IdentifierType] = [
    IdentifierType(
        id=uuid.UUID("e868f539ac1001062cfa029c4c5df4d0"),
        type="page",
    ),
]


def apply_edits(asset: Asset) -> Asset:
    metadata: dict = asset.get("metadata")
    metadata["displayName"] = "Annual Report 2025"
    metadata["teaser"] = (
        "Overview of the year's performance."
    )
    metadata["keywords"] = (
        str(metadata.get("keywords") or "").strip().lower()
    )
    return asset


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        for identifier in TARGETS:
            cascade.operations.read(identifier).edit(
                apply_edits
            )

        results = cascade.submit_requests(CascadeSuccess)

        for failure in results.failed:
            print(
                f"edit failed: {failure.identifier}: "
                f"{failure.message}"
            )
        print(
            f"Saved {len(results.success)}/{len(TARGETS)}."
        )


if __name__ == "__main__":
    main()

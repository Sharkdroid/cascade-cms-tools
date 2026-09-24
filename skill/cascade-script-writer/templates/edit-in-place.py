#!/usr/bin/env python3
"""Read assets, modify fields on the returned Asset objects,
then save them.

Asset writes are ATTRIBUTE assignment (`asset.displayName =
...`), never subscript assignment. `Asset` defines
`__setattr__` and `.get()` but no `__setitem__`, so
`asset["displayName"] = ...` raises TypeError. It also
rejects a type change on an existing field: if `name` is
currently a str, assigning an int raises TypeError.

One chain per target: `read(identifier).edit(identifier,
apply_edits)` reads the asset, then `edit()`'s callable
payload is invoked with that result to produce the saved
version. A chain that fails to read never reaches edit — its
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

TARGETS: list[IdentifierType] = [
    IdentifierType(
        id=uuid.UUID("e868f539ac1001062cfa029c4c5df4d0"),
        type="page",
    ),
]


def apply_edits(asset: Asset) -> Asset:
    asset.displayName = "Annual Report 2025"
    asset.teaser = "Overview of the year's performance."
    asset.keywords = (
        (asset.get("keywords") or "").strip().lower()
    )
    return asset


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        for identifier in TARGETS:
            cascade.operations.read(identifier).edit(
                identifier, apply_edits
            )

        results = cascade.submit_requests(CascadeSuccess)

        print(f"Saved {len(results.success)}.")


if __name__ == "__main__":
    main()

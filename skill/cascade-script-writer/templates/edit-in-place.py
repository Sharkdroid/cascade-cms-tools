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
slot in the results is the `CascadeError` instead.
"""

import os
import uuid
from typing import Any

from cascade_cms.cmstypes import (
    Asset,
    CascadeError,
    CascadeSuccess,
    IdentifierType,
)
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
        environment_variables, configuration_variables
    ) as cascade:
        for identifier in TARGETS:
            cascade.operations.read(identifier).edit(
                identifier, apply_edits
            )

        try:
            results = cascade.submit_requests(
                CascadeSuccess
            )
        except Exception as exc:
            print(f"Batch failed: {exc}")
            return

        for result in results:
            if isinstance(result, CascadeError):
                print(f"FAILED: {result.message}")
            elif isinstance(result, Exception):
                print(f"FAILED: {result}")
            else:
                print("Saved.")


if __name__ == "__main__":
    main()

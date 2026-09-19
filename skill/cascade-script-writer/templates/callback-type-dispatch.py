#!/usr/bin/env python3
"""Dispatch on result type inside a callback.

One batch can mix result types, and every operation can also
come back as a CascadeError instead of its success type —
failures are returned as values, not raised. Results arrive
in COMPLETION order, not submission order, so never match a
result to its request by position.
"""

import os
import uuid
from typing import Any

from cascade_cms.cmstypes import (
    Asset,
    CascadeError,
    CascadeSuccess,
    CheckedOutAsset,
    IdentifierType,
    ListElements,
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


def dispatch(result: object) -> None:
    # CascadeError first: it is the one type any operation
    # can return.
    if isinstance(result, CascadeError):
        print(f"ERROR: {result.message}")
    elif isinstance(result, CascadeSuccess):
        print("WRITE OK")
    elif isinstance(result, Asset):
        path = result.get("path")
        print(f"ASSET {result.asset_type}: {path}")
    elif isinstance(result, IdentifierType):
        print(f"CREATED {result.get_type} {result.get_id}")
    elif isinstance(result, CheckedOutAsset):
        working_copy = result.workingCopyIdentifier
        print(f"CHECKED OUT -> {working_copy.get_id}")
    elif isinstance(result, ListElements):
        print(f"LIST of {len(result.flat)}")
    else:
        print(f"UNHANDLED {type(result).__name__}")


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(dispatch)
        cascade.operations.listSites()

        try:
            cascade.submit_requests()
        except Exception as exc:
            print(f"Request submission failed: {exc}")


if __name__ == "__main__":
    main()

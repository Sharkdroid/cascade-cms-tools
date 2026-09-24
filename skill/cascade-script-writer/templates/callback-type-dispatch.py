#!/usr/bin/env python3
"""Dispatch on result type inside a callback.

One batch can mix result types, so a callback can dispatch
on what it receives. A chain that fails at an operation
never reaches its callbacks: the wrapper records it and
reports it at exit, so no CascadeError branch is needed.
"""

import os
import uuid

from cascade_cms.cmstypes import (
    Asset,
    CascadeSuccess,
    CheckedOutAsset,
    IdentifierType,
    ListElements,
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


def dispatch(result: object) -> None:
    if isinstance(result, CascadeSuccess):
        print("WRITE OK")
    elif isinstance(result, Asset):
        path = result.get("path")
        print(f"ASSET {result.asset_type}: {path}")
    elif isinstance(result, IdentifierType):
        print(f"CREATED {result.get_type} {result.get_id}")
    elif isinstance(result, CheckedOutAsset):
        working_copy = result.working_copy_identifier
        print(f"CHECKED OUT -> {working_copy.get_id}")
    elif isinstance(result, ListElements):
        print(f"LIST of {len(result.flat)}")
    else:
        print(f"UNHANDLED {type(result).__name__}")


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(dispatch)
        cascade.operations.listSites()

        cascade.submit_requests()


if __name__ == "__main__":
    main()

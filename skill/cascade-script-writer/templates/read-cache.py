#!/usr/bin/env python3
"""Read the same assets twice to show the GET response
cache.
"""

import os
import uuid
from typing import Any

from cascade_cms.cmstypes import (
    Asset,
    CascadeError,
    IdentifierType,
)
from cascade_cms.wrapper import CascadeWrapperBase

# ----- Configuration -----
environment_variables: dict[str, str] = {
    "API_KEY": os.environ["CASCADE_API_KEY"],
    "CASCADE_URL": os.environ["CASCADE_URL"],
    "SERVER": os.environ.get("SERVER", "default"),
}
# Only GETs are cacheable, and only 200s are stored — so
# reads are served from SQLite on the second pass while
# every write still hits the server.
configuration_variables: dict[str, Any] = {
    "cache_name": "./cache/cache.sqlite",
    "allowed_codes": (200,),
    "allowed_methods": ("GET",),
    "expire_after": 3600,
}

TARGETS: list[IdentifierType] = [
    IdentifierType(
        id=uuid.UUID("e868f539ac1001062cfa029c4c5df4d0"),
        type="page",
    ),
    IdentifierType(
        id=uuid.UUID("e868f5b1ac1001062cfa029c9b8b4f3e"),
        type="page",
    ),
]


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        for pass_number in (1, 2):
            cascade.operations.read(TARGETS)

            try:
                results = cascade.submit_requests(Asset)
            except Exception as exc:
                print(f"Pass {pass_number} failed: {exc}")
                return

            hits = sum(
                1
                for r in results
                if not isinstance(r, CascadeError)
            )
            print(
                f"Pass {pass_number}: "
                f"{hits}/{len(TARGETS)} assets read"
            )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Handle results with a plain loop instead of a callback.

Callbacks are optional. When the work is simple and
sequential, reading submit_requests()'s return value
directly is clearer than a .then() chain.
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
    IdentifierType(
        id=uuid.UUID("e868f5b1ac1001062cfa029c9b8b4f3e"),
        type="page",
    ),
]


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read(TARGETS)

        try:
            results = cascade.submit_requests(Asset)
        except Exception as exc:
            print(f"Request submission failed: {exc}")
            return

        for result in results:
            if isinstance(result, CascadeError):
                print(f"FAILED: {result.message}")
                continue
            path = result.get("path")
            title = result.get("title")
            print(f"{path} — {title}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Accumulate results safely across concurrently-running
callbacks.

Callbacks run concurrently across results, and sync ones run
in a ThreadPoolExecutor by default — so a shared accumulator
is touched from several threads. Guard it with a Lock. (A
ProcessPoolExecutor would not share memory at all: each
process gets its own copy and updates are lost.)
"""

import os
import threading
import uuid
from typing import Any

from cascade_cms.cmstypes import (
    Asset,
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

_lock: threading.Lock = threading.Lock()
totals: dict[str, int] = {}


def tally_by_type(result: Asset) -> None:
    # A failed read never reaches the callback; the
    # library counts it and reports it at exit.
    key = result.asset_type
    with _lock:
        totals[key] = totals.get(key, 0) + 1


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(tally_by_type)

        cascade.submit_requests(Asset)

        for key, count in sorted(totals.items()):
            print(f"{key}: {count}")


if __name__ == "__main__":
    main()

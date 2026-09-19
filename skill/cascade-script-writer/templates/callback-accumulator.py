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

_lock: threading.Lock = threading.Lock()
totals: dict[str, int] = {}


def tally_by_type(result: Asset | CascadeError) -> None:
    if isinstance(result, CascadeError):
        key = "error"
    else:
        key = result.asset_type
    with _lock:
        totals[key] = totals.get(key, 0) + 1


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(tally_by_type)

        try:
            cascade.submit_requests(Asset)
        except Exception as exc:
            print(f"Request submission failed: {exc}")
            return

        for key, count in sorted(totals.items()):
            print(f"{key}: {count}")


if __name__ == "__main__":
    main()

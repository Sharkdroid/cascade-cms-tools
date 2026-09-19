#!/usr/bin/env python3
"""Report progress from a callback.

Progress is a count of completions, not a position in the
submitted list: results arrive in COMPLETION order, so "item
3 of 10" refers to the third result to finish, not the third
asset queued. Print counts, never indexes into the request
list.
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
_state: dict[str, int] = {"done": 0, "errors": 0}


def report_progress(result: Asset | CascadeError) -> None:
    with _lock:
        _state["done"] += 1
        if isinstance(result, CascadeError):
            _state["errors"] += 1
        done = _state["done"]
    print(f"[{done}/{len(TARGETS)}] completed")


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(
            report_progress
        )

        try:
            cascade.submit_requests(Asset)
        except Exception as exc:
            print(f"Request submission failed: {exc}")
            return

        print(
            f"Done: {_state['done']} completed, "
            f"{_state['errors']} failed."
        )


if __name__ == "__main__":
    main()

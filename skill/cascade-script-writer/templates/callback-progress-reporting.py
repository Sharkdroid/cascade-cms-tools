#!/usr/bin/env python3
"""Report progress from a callback.

Progress is a count of completions, not a position in the
submitted list: chains finish in any order, so "3 of 10"
means the third to finish, not the third asset queued.
Print counts, never indexes into the request list. A read
that fails never reaches the callback; the wrapper tallies
it at exit.
"""

import os
import threading
import uuid

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
_state: dict[str, int] = {"done": 0}


def report_progress(result: Asset) -> None:
    with _lock:
        _state["done"] += 1
        done = _state["done"]
    print(f"[{done}/{len(TARGETS)}] completed")


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(
            report_progress
        )

        cascade.submit_requests(Asset)

        print(f"Done: {_state['done']} completed.")


if __name__ == "__main__":
    main()

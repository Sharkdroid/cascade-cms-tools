#!/usr/bin/env python3
"""Run CPU-bound callbacks in a ProcessPoolExecutor.

Sync callbacks run in an executor so they never block the
event loop. The default is a ThreadPoolExecutor, which is
right for I/O but useless for CPU-bound work under the GIL —
pass a ProcessPoolExecutor for that.

A ProcessPoolExecutor pickles the callback and its argument,
so the callback must be a module-level function (not a
closure or lambda).
"""

import os
import uuid
from concurrent.futures import ProcessPoolExecutor

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


def analyze_content(result: Asset) -> None:
    """Deliberately CPU-heavy work — the reason for a
    process pool.
    """
    body = result.get("xhtml") or ""
    word_count = len(body.split())
    checksum = sum(ord(c) for c in body) % 100000
    path = result.get("path")
    print(
        f"{path}: {word_count} words, checksum {checksum}"
    )


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(
            analyze_content
        )

        with ProcessPoolExecutor(
            max_workers=os.cpu_count()
        ) as executor:
            cascade.submit_requests(
                Asset, executor=executor
            )


if __name__ == "__main__":
    main()

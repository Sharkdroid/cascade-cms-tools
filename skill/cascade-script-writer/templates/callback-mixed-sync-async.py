#!/usr/bin/env python3
"""Mix sync and async callbacks on one operation.

Each callback is inspected independently: async ones are
awaited, sync ones are handed to the executor. They still
run in registration order per result, so a sync callback's
mutation is visible to the async callback after it.
"""

import asyncio
import os
import uuid

from cascade_cms.cmstypes import (
    Asset,
    IdentifierType,
)
from cascade_cms.wrapper import (
    Cascade,
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


def stamp_summary(result: Asset) -> None:
    """Sync: runs in the executor. summary and title
    live under metadata; edit them through the live dict.
    """
    metadata: dict = result.get("metadata")
    title = metadata.get("title") or "untitled"
    metadata["summary"] = f"Reviewed: {title}"


async def ship_summary(
    result: Asset,
) -> None:
    """Async: awaited directly, and sees stamp_summary's
    mutation.
    """
    await asyncio.sleep(0)
    metadata: dict = result.get("metadata")
    print(
        f"{result.get('path')} -> {metadata.get('summary')}"
    )


def main() -> None:
    with Cascade(environment_variables) as cascade:
        cascade.operations.read(TARGETS).then(
            [stamp_summary, ship_summary]
        )

        cascade.submit_requests(Asset)


if __name__ == "__main__":
    main()

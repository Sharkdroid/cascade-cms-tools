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
]


def stamp_summary(result: Asset | CascadeError) -> None:
    """Sync: runs in the executor."""
    if isinstance(result, CascadeError):
        return
    result.summary = (
        f"Reviewed: {result.get('title') or 'untitled'}"
    )


async def ship_summary(
    result: Asset | CascadeError,
) -> None:
    """Async: awaited directly, and sees stamp_summary's
    mutation.
    """
    if isinstance(result, CascadeError):
        return
    await asyncio.sleep(0)
    print(
        f"{result.get('path')} -> {result.get('summary')}"
    )


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(
            [stamp_summary, ship_summary]
        )

        try:
            cascade.submit_requests(Asset)
        except Exception as exc:
            print(f"Request submission failed: {exc}")


if __name__ == "__main__":
    main()

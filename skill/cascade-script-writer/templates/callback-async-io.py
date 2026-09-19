#!/usr/bin/env python3
"""Use an async callback for I/O.

An async callback is awaited directly on the event loop — no
executor is involved. Use this when the work is already
awaitable (an HTTP call, an async DB driver). Never call
blocking I/O inside an async callback: that stalls the loop
and every other in-flight result. Use a sync callback for
blocking work.
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
    IdentifierType(
        id=uuid.UUID("e868f5b1ac1001062cfa029c9b8b4f3e"),
        type="page",
    ),
]


async def notify_downstream(
    result: Asset | CascadeError,
) -> None:
    if isinstance(result, CascadeError):
        return
    # Stand-in for a real awaitable call (aiohttp POST,
    # async queue publish...).
    await asyncio.sleep(0)
    print(f"notified: {result.get('path')}")


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(
            notify_downstream
        )

        try:
            cascade.submit_requests(Asset)
        except Exception as exc:
            print(f"Request submission failed: {exc}")


if __name__ == "__main__":
    main()

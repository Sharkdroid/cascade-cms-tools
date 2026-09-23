#!/usr/bin/env python3
"""Let a callback select assets for a second publish pass.

A callback runs AFTER its batch has finished, so anything it
queues would sit unsent. Collect during the first pass,
queue and submit in a second — one submit_requests() call
per batch.
"""

import os
import threading
import uuid
from typing import Any

from cascade_cms.cmstypes import (
    Asset,
    CascadeSuccess,
    IdentifierType,
    publishInformation,
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
to_publish: list[IdentifierType] = []


def select_stale(result: Asset) -> None:
    if result.get("shouldBePublished") and not result.get(
        "published"
    ):
        asset_id = result.get("id")
        if not asset_id:
            return
        with _lock:
            to_publish.append(
                IdentifierType(
                    id=uuid.UUID(asset_id),
                    type=result.asset_type,
                )
            )


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(select_stale)

        cascade.submit_requests(Asset)

        if not to_publish:
            print("Nothing needs publishing.")
            return

        cascade.operations.publish(
            to_publish, publishInformation(unpublish=False)
        )

        results = cascade.submit_requests(CascadeSuccess)

        ok = len(results.success)
        print(f"Published {ok}/{len(to_publish)}.")


if __name__ == "__main__":
    main()

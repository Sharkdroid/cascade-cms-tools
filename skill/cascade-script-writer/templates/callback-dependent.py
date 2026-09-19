#!/usr/bin/env python3
"""Use a callback to collect work for a second, dependent
batch.

A callback cannot see results that have not arrived yet, so
anything that depends on the whole batch belongs after
submit_requests() returns. Here the callback only
accumulates; the follow-up operations are queued afterwards.
"""

import os
import uuid
from typing import Any

from cascade_cms.cmstypes import (
    Asset,
    CascadeError,
    CascadeSuccess,
    IdentifierType,
    publishInformation,
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

ready_to_publish: list[IdentifierType] = []


def collect_published(result: Asset | CascadeError) -> None:
    if isinstance(result, CascadeError):
        return
    if result.get("shouldBePublished"):
        path = result.get("path")
        site = result.get("siteName")
        if path and site:
            ready_to_publish.append(
                IdentifierType(
                    id=uuid.UUID(result.get("id")),
                    type=result.asset_type,
                )
            )


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(
            collect_published
        )

        try:
            cascade.submit_requests(Asset)
        except Exception as exc:
            print(f"Read failed: {exc}")
            return

        if not ready_to_publish:
            print("Nothing to publish.")
            return

        cascade.operations.publish(
            ready_to_publish,
            publishInformation(unpublish=False),
        )

        try:
            results = cascade.submit_requests(
                CascadeSuccess
            )
        except Exception as exc:
            print(f"Publish failed: {exc}")
            return

        ok = sum(
            1
            for r in results
            if not isinstance(r, CascadeError)
        )
        print(f"Published {ok}.")


if __name__ == "__main__":
    main()

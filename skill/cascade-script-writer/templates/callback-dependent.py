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

TARGETS: list[IdentifierType] = [
    IdentifierType(
        id=uuid.UUID("e868f539ac1001062cfa029c4c5df4d0"),
        type="page",
    ),
]

ready_to_publish: list[IdentifierType] = []


def collect_published(result: Asset) -> None:
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
        environment_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(
            collect_published
        )

        reads = cascade.submit_requests(Asset)
        # A failed read does not stop the block; skip the
        # publish so it never runs on a partial set.
        if reads.failed:
            return

        if not ready_to_publish:
            print("Nothing to publish.")
            return

        cascade.operations.publish(
            ready_to_publish,
            publishInformation(unpublish=False),
        )

        results = cascade.submit_requests(CascadeSuccess)

        ok = len(results.success)
        print(f"Published {ok}.")


if __name__ == "__main__":
    main()

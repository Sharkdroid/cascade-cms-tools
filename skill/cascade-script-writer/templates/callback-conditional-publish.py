#!/usr/bin/env python3
"""Let a callback select assets for a second publish pass.

A callback runs AFTER its batch has finished, so anything it
queues would sit unsent. Collect during the first pass,
queue and submit in a second — one submit_requests() call
per batch.

A page is stale when shouldBePublished is true and it was
never published or changed since its last publish. Live
Cascade has no "published" key. lastPublishedDate is
MISSING on a never-published page (not null), and
Asset.get raises KeyError on a missing key, so every
optional read goes through optional_field(). Dates are
ISO 8601 UTC with milliseconds and a Z; datetime.
fromisoformat parses them. A date that fails to parse
raises: it is never guessed.
"""

import os
import threading
import uuid
from datetime import datetime

from cascade_cms.cmstypes import (
    Asset,
    AssetTypes,
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

# The type this script reads and publishes. Build every
# identifier from it: internal_type is a response key, not
# a request type, and is rejected for some assets.
TARGET_TYPE: AssetTypes = "page"

TARGETS: list[IdentifierType] = [
    IdentifierType(
        id=uuid.UUID("e868f539ac1001062cfa029c4c5df4d0"),
        type=TARGET_TYPE,
    ),
    IdentifierType(
        id=uuid.UUID("e868f5b1ac1001062cfa029c9b8b4f3e"),
        type=TARGET_TYPE,
    ),
]

_lock: threading.Lock = threading.Lock()
to_publish: list[IdentifierType] = []


def optional_field(asset: Asset, key: str) -> object:
    """Return asset[key], or None when the key is absent."""
    try:
        return asset.get(key)
    except KeyError:
        return None


def is_stale(asset: Asset) -> bool:
    if not optional_field(asset, "shouldBePublished"):
        return False
    published = optional_field(asset, "lastPublishedDate")
    if published is None:
        return True  # never published
    modified = optional_field(asset, "lastModifiedDate")
    if modified is None:
        return False
    return datetime.fromisoformat(
        str(modified)
    ) > datetime.fromisoformat(str(published))


def select_stale(result: Asset) -> None:
    if not is_stale(result):
        return
    asset_id = optional_field(result, "id")
    if not asset_id:
        return
    with _lock:
        to_publish.append(
            IdentifierType(
                id=uuid.UUID(str(asset_id)),
                type=TARGET_TYPE,
            )
        )


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
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

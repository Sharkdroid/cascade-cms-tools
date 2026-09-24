#!/usr/bin/env python3
"""Mutate structured-data nodes in a callback, then save.

get_data_structure(group, identifier) returns matching nodes
BY REFERENCE — mutating a returned node mutates the asset
itself.

One chain per target: `read(identifier).edit(identifier,
update_contact)` reads the asset, then `edit()`'s callable
payload (`update_contact`) is invoked with that result — it
mutates and returns the asset, which is what gets saved.
Nothing is sent until `submit_requests()` runs the whole
batch.
"""

import os
import uuid

from cascade_cms.cmstypes import (
    Asset,
    CascadeSuccess,
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
]

GROUP: str = "contact-block"
FIELD: str = "phone"
NEW_VALUE: str = "+1 555 0100"


def update_contact(asset: Asset) -> Asset:
    nodes = asset.get_data_structure(GROUP, FIELD)
    for node in nodes or []:
        # By reference: this edits the asset in place.
        node["text"] = NEW_VALUE
    return asset


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        for identifier in TARGETS:
            cascade.operations.read(identifier).edit(
                identifier, update_contact
            )

        results = cascade.submit_requests(CascadeSuccess)

        print(f"Saved {len(results.success)}.")


if __name__ == "__main__":
    main()

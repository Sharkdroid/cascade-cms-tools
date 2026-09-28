#!/usr/bin/env python3
"""Edit one structured-data field, safely.

- Address one group and one field; never the whole
  structure (no get/print/return/assign of
  structuredData).
- Names come from live data. If the Cascade MCP is
  connected, confirm them with
  cascade_get_data_structure; else ask the user.
- A None or wrong count RAISES: a typo would otherwise
  edit nothing and still report success.
- Group identifiers can repeat and nest; every match
  is edited.
- A raise here is logged as [CASCADE-REST-CMS]
  (LIBRARY) with your message after "ValueError:".
  The prefix does not mean a library bug.
- Writes are delivered in stages (SKILL.md Step 6).
  Confirm the node's live shape first; this template
  edits free-text fields only (schema type null, not
  a radio button or other chooser).

get_data_structure(group, identifier) returns matching
nodes BY REFERENCE, so setting node["text"] edits the
asset itself. One chain per target:
`read(identifier).edit(update_node)`.
"""

import os
import uuid

from cascade_cms.cmstypes import (
    Asset,
    CascadeSuccess,
    IdentifierType,
)
from cascade_cms.utils import script_log
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
EXPECTED_COUNT: int = 1


def update_node(asset: Asset) -> Asset:
    nodes = asset.get_data_structure(GROUP, FIELD)
    if not nodes:
        raise ValueError(f"no {GROUP}/{FIELD} node")
    if len(nodes) != EXPECTED_COUNT:
        raise ValueError(
            f"expected {EXPECTED_COUNT} node(s), "
            f"found {len(nodes)}"
        )
    # Count only; never log the values.
    script_log.note(
        f"set {GROUP}/{FIELD} on {asset.get('id')}: "
        f"{len(nodes)} node(s)"
    )
    for node in nodes:
        # By reference: this edits the asset in place.
        node["text"] = NEW_VALUE
    return asset


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        for identifier in TARGETS:
            cascade.operations.read(identifier).edit(
                update_node
            )

        results = cascade.submit_requests(CascadeSuccess)

        print(f"Saved {len(results.success)}.")
        for failure in results.failed:
            print(
                f"failed: {failure.identifier}: "
                f"{failure.message}"
            )


if __name__ == "__main__":
    main()

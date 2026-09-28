#!/usr/bin/env python3
"""Edit assets you read EARLIER in this script.

Prefer `read(x).edit(fn)` (see edit-in-place): one chain,
one submit, fresh data. This template is the one exception:
assets read earlier and held in a variable may be edited
LATER with `edit(asset)`, ONE edit() call per asset.

Caveats:
- A held Asset is a SNAPSHOT. The edit overwrites whatever
  changed in Cascade in the meantime.
- Keep the gap short. Re-read if anything in between could
  change those assets. The validator cannot enforce this.
- Do not zip `.success` against your inputs; report
  `results.failed` (each has an identifier and message).

Writes are delivered in stages (SKILL.md Step 6).
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

# Placeholder: targets can come from anywhere.
TARGETS: list[IdentifierType] = [
    IdentifierType(
        id=uuid.UUID("e868f539ac1001062cfa029c4c5df4d0"),
        type="page",
    ),
]


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        # Submit 1: read and hold the assets.
        cascade.operations.read(TARGETS)
        read_results = cascade.submit_requests(Asset)
        held = read_results.success
        for failure in read_results.failed:
            print(
                f"read failed: {failure.identifier}: "
                f"{failure.message}"
            )

        # Other work goes here: in memory, or another
        # submit. Keep it short so the snapshots stay
        # fresh.

        # Submit 2: one edit() per held asset.
        for asset in held:
            asset.displayName = "Annual Report 2025"
            cascade.operations.edit(asset)
        results = cascade.submit_requests(CascadeSuccess)

        for failure in results.failed:
            print(
                f"edit failed: {failure.identifier}: "
                f"{failure.message}"
            )
        print(f"Saved {len(results.success)}/{len(held)}.")


if __name__ == "__main__":
    main()

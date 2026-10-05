#!/usr/bin/env python3
"""Walk a folder tree, one LEVEL per submit.

Enumerating a tree needs only folder reads: each `children`
entry already carries id, type and path. So barriers equal
tree depth, not folder count. Every folder at the current
level is read in ONE batch; the level loop is the
deliberate barrier (marked `# barrier:` on the
loop header). Failed reads are printed, not hidden.

Read-only: results go to stdout, no files. Staging (SKILL.md
Step 6) does not apply.
"""

import os
import uuid

from cascade_cms.cmstypes import Asset, IdentifierType
from cascade_cms.utils import to_identifiers
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

# Placeholder root folder. Use an id (or a site+path
# identifier for the folder), not Path("/").
ROOT: IdentifierType = IdentifierType(
    id=uuid.UUID("e868f539ac1001062cfa029c4c5df4d0"),
    type="folder",
)
MAX_DEPTH: int = 10


def child_identifiers(
    asset: Asset,
) -> list[IdentifierType]:
    """Pure: raw children entries to identifiers."""
    try:
        raw = asset.get("children")
    except KeyError:
        raw = None
    return to_identifiers(raw)


def main() -> None:
    seen: set[uuid.UUID] = {ROOT.get_id}
    others: dict[str, list[IdentifierType]] = {}
    level: list[IdentifierType] = [ROOT]
    depth = 0

    with Cascade(environment_variables) as cascade:
        while level:  # barrier: per level
            if depth >= MAX_DEPTH:
                break
            cascade.operations.read(level)
            reads = cascade.submit_requests(Asset)
            # A failed folder read loses its subtree.
            for failure in reads.failed:
                print(
                    f"read failed: {failure.identifier}: "
                    f"{failure.message}"
                )
            folders = reads.success

            next_level: list[IdentifierType] = []
            for folder in folders:
                for kid in child_identifiers(folder):
                    if kid.get_id in seen:
                        continue
                    seen.add(kid.get_id)
                    if kid.get_type == "folder":
                        next_level.append(kid)
                    else:
                        others.setdefault(
                            kid.get_type, []
                        ).append(kid)

            depth += 1
            print(
                f"level {depth}: read {len(level)} "
                f"folders, found {len(next_level)} more"
            )
            level = next_level

    for kind, found in sorted(others.items()):
        print(f"{kind}: {len(found)}")


if __name__ == "__main__":
    main()

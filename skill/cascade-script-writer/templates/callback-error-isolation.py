#!/usr/bin/env python3
"""Keep going when one result's processing fails.

An uncaught exception in a callback stops THAT chain only.
The other chains finish, the wrapper prints its tally, and
the first callback exception is raised, unwrapped, when the
`with` block exits (exit code 1).

For tolerant processing, catch errors inside the callback
and record them, as below. The run then finishes normally
and you decide what a partial failure means.
"""

import os
import uuid
from typing import Any

from cascade_cms.cmstypes import (
    Asset,
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

processed: list[str] = []
failed: list[str] = []


def risky_transform(result: Asset) -> None:
    path = result.get("path") or "<unknown>"
    try:
        # Anything that can throw on unexpected data — a
        # missing field, a bad parse, an external call.
        title = result.get("title")
        if title is None:
            raise ValueError("asset has no title")
        result.title = title.strip()
    except Exception as exc:
        # Catch locally: uncaught, this would stop the
        # chain and be raised at exit.
        failed.append(f"{path}: {exc}")
        return
    processed.append(path)


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(
            risky_transform
        )

        results = cascade.submit_requests(Asset)

        readable = len(results.success)
        print(
            f"read ok: {readable}, "
            f"transformed: {len(processed)}, "
            f"failed: {len(failed)}"
        )
        for line in failed:
            print(f"  FAILED {line}")


if __name__ == "__main__":
    main()

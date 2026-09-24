#!/usr/bin/env python3
"""Chain several callbacks onto one operation.

Callbacks run sequentially per result (result1 -> cb1 ->
cb2), but concurrently across results. Each callback
receives one result object.
"""

import os
import uuid

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

TARGETS: list[IdentifierType] = [
    IdentifierType(
        id=uuid.UUID("e868f539ac1001062cfa029c4c5df4d0"),
        type="page",
    ),
]


def log_read(result: Asset) -> None:
    print(f"read: {result.get('path')}")


def normalize_keywords(
    result: Asset,
) -> None:
    raw = result.get("keywords") or ""
    cleaned = ", ".join(
        k.strip().lower()
        for k in raw.split(",")
        if k.strip()
    )
    # Attribute assignment — Asset has no __setitem__.
    result.keywords = cleaned


def report(result: Asset) -> None:
    print(f"{result.get('path')}: {result.get('keywords')}")


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(
            log_read
        ).then([normalize_keywords, report])

        cascade.submit_requests(Asset)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Chain several callbacks onto one operation.

Callbacks run sequentially per result (result1 -> cb1 ->
cb2), but concurrently across results. Each callback
receives one result object.
"""

import os
import uuid
from typing import Any

from cascade_cms.cmstypes import (
    Asset,
    CascadeError,
    IdentifierType,
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


def skip_errors(result: Asset | CascadeError) -> None:
    if isinstance(result, CascadeError):
        print(f"FAILED: {result.message}")


def normalize_keywords(
    result: Asset | CascadeError,
) -> None:
    if isinstance(result, CascadeError):
        return
    raw = result.get("keywords") or ""
    cleaned = ", ".join(
        k.strip().lower()
        for k in raw.split(",")
        if k.strip()
    )
    # Attribute assignment — Asset has no __setitem__.
    result.keywords = cleaned


def report(result: Asset | CascadeError) -> None:
    if isinstance(result, CascadeError):
        return
    print(f"{result.get('path')}: {result.get('keywords')}")


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(
            skip_errors
        ).then([normalize_keywords, report])

        try:
            cascade.submit_requests(Asset)
        except Exception as exc:
            print(f"Request submission failed: {exc}")


if __name__ == "__main__":
    main()

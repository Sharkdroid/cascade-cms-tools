#!/usr/bin/env python3
"""Detect partial failure when a callback raises.

A callback that raises is logged and swallowed — the batch
continues to the next callback and the next result, and
submit_requests() still returns normally. That means a
crashed callback is INVISIBLE unless the script tracks its
own outcomes. Record successes and failures explicitly and
reconcile the counts afterwards.
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
    IdentifierType(
        id=uuid.UUID("e868f5b1ac1001062cfa029c9b8b4f3e"),
        type="page",
    ),
]

processed: list[str] = []
failed: list[str] = []


def risky_transform(result: Asset | CascadeError) -> None:
    if isinstance(result, CascadeError):
        return
    path = result.get("path") or "<unknown>"
    try:
        # Anything that can throw on unexpected data — a
        # missing field, a bad parse, an external call.
        title = result.get("title")
        if title is None:
            raise ValueError("asset has no title")
        result.title = title.strip()
    except Exception as exc:
        # Catch locally: the library would otherwise swallow
        # this silently.
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

        try:
            results = cascade.submit_requests(Asset)
        except Exception as exc:
            print(f"Request submission failed: {exc}")
            return

        readable = sum(
            1
            for r in results
            if not isinstance(r, CascadeError)
        )
        print(
            f"read ok: {readable}, "
            f"transformed: {len(processed)}, "
            f"failed: {len(failed)}"
        )
        for line in failed:
            print(f"  FAILED {line}")
        if len(processed) + len(failed) != readable:
            print(
                "WARNING: some callbacks did not "
                "run to completion."
            )


if __name__ == "__main__":
    main()

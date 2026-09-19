#!/usr/bin/env python3
"""Stream results to a CSV from a callback.

Writing to a file is I/O-bound, so a plain sync callback on
the default ThreadPoolExecutor is the right choice.
csv.writer is not thread-safe and callbacks run concurrently
across results — hold a lock around each write.
"""

import csv
import os
import threading
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

OUTPUT_CSV: str = "./asset_export.csv"
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

_lock: threading.Lock = threading.Lock()


def main() -> None:
    with open(
        OUTPUT_CSV, "w", newline="", encoding="utf-8"
    ) as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["path", "type", "title", "lastModified"]
        )

        def export_row(
            result: Asset | CascadeError,
        ) -> None:
            if isinstance(result, CascadeError):
                return
            with _lock:
                writer.writerow(
                    [
                        result.get("path"),
                        result.asset_type,
                        result.get("title"),
                        result.get("lastModified"),
                    ]
                )

        with CascadeWrapperBase(
            environment_variables, configuration_variables
        ) as cascade:
            cascade.operations.read(TARGETS).then(
                export_row
            )

            try:
                cascade.submit_requests(Asset)
            except Exception as exc:
                print(f"Request submission failed: {exc}")
                return

    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()

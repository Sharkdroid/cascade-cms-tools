#!/usr/bin/env python3
"""Read several assets by UUID and by site+path, then print
what came back.
"""

import os
import uuid
from typing import Any

from cascade_cms.cmstypes import (
    Asset,
    CascadeError,
    IdentifierType,
    Path,
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

SITE_NAME: str = "www"

# Two interchangeable ways to name an asset. Use
# IdentifierType when you already hold the UUID; use Path
# when you only know where the asset lives.
BY_ID: IdentifierType = IdentifierType(
    id=uuid.UUID("e868f539ac1001062cfa029c4c5df4d0"),
    type="page",
)
BY_PATH: Path = {
    "asset_type": "page",
    # Required: resolve_identifier() raises without it.
    "siteName": SITE_NAME,
    "path": "about/index",
    "siteId": uuid.UUID("00000000000000000000000000000000"),
}


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read([BY_ID, BY_PATH])

        try:
            results = cascade.submit_requests(Asset)
        except Exception as exc:
            print(f"Request submission failed: {exc}")
            return

        for result in results:
            if isinstance(result, CascadeError):
                print(f"FAILED: {result.message}")
            else:
                name = result.get("name")
                print(f"{result.asset_type}: {name}")


if __name__ == "__main__":
    main()

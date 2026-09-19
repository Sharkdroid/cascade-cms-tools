#!/usr/bin/env python3
"""Audit page-configuration regions in a callback.

get_page_configuration(name) returns a PageConfiguration;
passing a region name too returns that single PageRegion.
Both come back BY REFERENCE as Pydantic models, so assigning
to `.content` edits the asset in place. This template only
reads.
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

CONFIGURATION: str = "ASPX"
REQUIRED_REGION: str = "FOOTER"


def audit_regions(result: Asset | CascadeError) -> None:
    if isinstance(result, CascadeError):
        print(f"ERROR: {result.message}")
        return

    path = result.get("path")
    config = result.get_page_configuration(CONFIGURATION)
    if config is None:
        print(f"{path}: no '{CONFIGURATION}' configuration")
        return

    region = result.get_page_configuration(
        CONFIGURATION, REQUIRED_REGION
    )
    if region is None:
        print(
            f"{path}: '{CONFIGURATION}' is missing "
            f"region '{REQUIRED_REGION}'"
        )
        return

    filled = bool(region.content and region.content.strip())
    status = "populated" if filled else "EMPTY"
    print(f"{path}: {REQUIRED_REGION} {status}")


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(audit_regions)

        try:
            cascade.submit_requests(Asset)
        except Exception as exc:
            print(f"Request submission failed: {exc}")


if __name__ == "__main__":
    main()

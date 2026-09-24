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

CONFIGURATION: str = "ASPX"
REQUIRED_REGION: str = "FOOTER"


def audit_regions(result: Asset) -> None:
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
        environment_variables
    ) as cascade:
        cascade.operations.read(TARGETS).then(audit_regions)

        cascade.submit_requests(Asset)


if __name__ == "__main__":
    main()

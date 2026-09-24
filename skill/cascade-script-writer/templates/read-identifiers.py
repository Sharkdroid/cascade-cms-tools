#!/usr/bin/env python3
"""Read several assets by UUID and by site+path, then print
what came back.
"""

import os
import uuid

from cascade_cms.cmstypes import (
    Asset,
    IdentifierType,
    Path,
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

SITE_NAME: str = "www"

# Two interchangeable ways to name an asset. Use
# IdentifierType when you already hold the UUID; use Path
# when you only know where the asset lives.
BY_ID: IdentifierType = IdentifierType(
    id=uuid.UUID("e868f539ac1001062cfa029c4c5df4d0"),
    type="page",
)
BY_PATH: Path = Path(
    asset_type="page",
    # Required: resolve_identifier() raises without it.
    site_name=SITE_NAME,
    path="about/index",
)


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        cascade.operations.read([BY_ID, BY_PATH])

        results = cascade.submit_requests(Asset)

        for result in results.success:
            name = result.get("name")
            print(f"{result.asset_type}: {name}")


if __name__ == "__main__":
    main()

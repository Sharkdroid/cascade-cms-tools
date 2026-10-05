#!/usr/bin/env python3
"""Search a site, then read every matching asset in a second
batch.
"""

import os

from cascade_cms.cmstypes import (
    Asset,
    AssetTypes,
    FieldsSearchTypes,
    IdentifierType,
    ListElements,
    SearchInformation,
)
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

SITE_NAME: str = "www"
# An inline list literal is inferred as list[str].
SEARCH_FIELDS: list[FieldsSearchTypes] = [
    "title",
    "keywords",
]
SEARCH_TYPES: list[AssetTypes] = ["page"]


def main() -> None:
    with Cascade(environment_variables) as cascade:
        cascade.operations.search(
            SearchInformation(
                site_name=SITE_NAME,
                search_terms="annual report",
                search_fields=SEARCH_FIELDS,
                search_types=SEARCH_TYPES,
            )
        )

        found = cascade.submit_requests(ListElements)

        # search returns ListElements containers, so flatten
        # to identifiers first.
        identifiers = [
            element
            for container in found.success
            for element in container.flat
            if isinstance(element, IdentifierType)
        ]
        if not identifiers:
            print("No matches.")
            return

        print(
            f"Found {len(identifiers)} match(es); "
            "reading them."
        )
        cascade.operations.read(identifiers)

        assets = cascade.submit_requests(Asset)

        for asset in assets.success:
            print(f"  {asset.get('path')}")


if __name__ == "__main__":
    main()

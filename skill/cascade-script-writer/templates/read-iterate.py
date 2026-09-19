#!/usr/bin/env python3
"""Search a site, then read every matching asset in a second
batch.
"""

import os
from typing import Any

from cascade_cms.cmstypes import (
    Asset,
    CascadeError,
    IdentifierType,
    ListElements,
    SearchInformation,
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


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.search(
            SearchInformation(
                siteName=SITE_NAME,
                searchTerms="annual report",
                searchFields=["title", "keywords"],
                searchTypes=["page"],
            )
        )

        try:
            found = cascade.submit_requests(ListElements)
        except Exception as exc:
            print(f"Search failed: {exc}")
            return

        # search returns ListElements containers, so flatten
        # to identifiers first.
        identifiers = [
            element
            for container in found
            if not isinstance(container, CascadeError)
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

        try:
            assets = cascade.submit_requests(Asset)
        except Exception as exc:
            print(f"Read failed: {exc}")
            return

        for asset in assets:
            if isinstance(asset, CascadeError):
                print(f"FAILED: {asset.message}")
            else:
                print(f"  {asset.get('path')}")


if __name__ == "__main__":
    main()

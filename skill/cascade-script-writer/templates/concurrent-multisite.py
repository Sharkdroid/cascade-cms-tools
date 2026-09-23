#!/usr/bin/env python3
"""Queue work across several sites in one batch.

Everything queued before submit_requests() runs concurrently
(bounded by the driver's semaphore), so one batch spanning
many sites beats a loop of batches.
"""

import os
from typing import Any

from cascade_cms.cmstypes import (
    IdentifierType,
    ListElements,
    SearchInformation,
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
configuration_variables: dict[str, Any] = {
    "cache_name": "./cache/cache.sqlite",
    "allowed_codes": (200,),
    "allowed_methods": ("GET",),
}

SITES: list[str] = ["www", "admissions", "research"]
SEARCH_TERM: str = "accreditation"


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        for site in SITES:
            cascade.operations.search(
                SearchInformation(
                    site_name=site,
                    search_terms=SEARCH_TERM,
                    search_types=["page"],
                )
            )

        results = cascade.submit_requests(ListElements)

        # Results are in queue order (one per site), so a
        # complete run can be zipped with SITES. Failed
        # sites are excluded from .success, so this reports
        # totals instead of per-site attribution.
        total = 0
        for container in results.success:
            total += sum(
                1
                for e in container.flat
                if isinstance(e, IdentifierType)
            )
        print(
            f"{total} match(es) across "
            f"{len(SITES)} site(s)."
        )


if __name__ == "__main__":
    main()

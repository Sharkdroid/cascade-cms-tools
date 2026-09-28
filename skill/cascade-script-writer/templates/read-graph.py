#!/usr/bin/env python3
"""Follow references level by level, with a memo dict.

Example chain: pages -> their content types (deduped, ONE
batch) -> the data definitions and metadata sets those
content types point to (ONE batch, both together). That is
3 submits however many pages there are.

Submits stay visible in main(); helpers are pure. The memo
maps id -> Asset so nothing is fetched twice. Fields:
page.contentTypeId; content type dataDefinitionId and
metadataSetId. `Asset.get()` has no default, so a possibly
missing field is guarded with try/except KeyError.

Read-only: prints to stdout. Staging (SKILL.md Step 6) does
not apply. If a later create needs this data, run this as
the earlier phase, then build the NewAsset.
"""

import os
import uuid

from cascade_cms.cmstypes import Asset, IdentifierType
from cascade_cms.failures import ChainResults
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

PAGES: list[IdentifierType] = [
    IdentifierType(
        id=uuid.UUID("e868f539ac1001062cfa029c4c5df4d0"),
        type="page",
    ),
]


def field_id(asset: Asset, field: str) -> str | None:
    try:
        value = asset.get(field)
    except KeyError:
        return None
    return str(value) if value else None


def report_failed(results: ChainResults[Asset]) -> None:
    for failure in results.failed:
        print(
            f"read failed: {failure.identifier}: "
            f"{failure.message}"
        )


def unseen(
    ids: dict[str, str], memo: dict[str, Asset]
) -> list[IdentifierType]:
    """Pure: identifiers (id -> type) not yet in memo."""
    return [
        IdentifierType(id=uuid.UUID(key), type=kind)
        for key, kind in ids.items()
        if key not in memo
    ]


def main() -> None:
    memo: dict[str, Asset] = {}
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        # Submit 1: the pages.
        cascade.operations.read(PAGES)
        page_results = cascade.submit_requests(Asset)
        report_failed(page_results)
        pages = page_results.success

        # Submit 2: content types, deduped.
        wanted: dict[str, str] = {}
        page_count: dict[str, int] = {}
        for page in pages:
            ct = field_id(page, "contentTypeId")
            if ct:
                wanted[ct] = "contenttype"
                page_count[ct] = page_count.get(ct, 0) + 1
        todo = unseen(wanted, memo)
        if todo:
            cascade.operations.read(todo)
            type_results = cascade.submit_requests(Asset)
            report_failed(type_results)
            for asset in type_results.success:
                memo[str(asset.get("id"))] = asset

        n_types = len(memo)

        # Submit 3: data definitions and metadata sets,
        # together (independent of each other).
        wanted = {}
        for key in list(memo):
            ct_asset = memo[key]
            dd = field_id(ct_asset, "dataDefinitionId")
            ms = field_id(ct_asset, "metadataSetId")
            if dd:
                wanted[dd] = "datadefinition"
            if ms:
                wanted[ms] = "metadataset"
        todo = unseen(wanted, memo)
        if todo:
            cascade.operations.read(todo)
            ref_results = cascade.submit_requests(Asset)
            report_failed(ref_results)
            for asset in ref_results.success:
                memo[str(asset.get("id"))] = asset

    print(f"pages: {len(pages)}")
    print(f"content types read: {n_types}")
    shared = [k for k, n in page_count.items() if n > 1]
    print(f"content types on 2+ pages: {len(shared)}")
    for key in shared:
        print(f"  {key}: {page_count[key]} pages")
    print(f"assets fetched in total: {len(memo)}")


if __name__ == "__main__":
    main()

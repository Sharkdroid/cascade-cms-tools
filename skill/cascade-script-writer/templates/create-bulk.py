#!/usr/bin/env python3
"""Create many assets in one batch from CSV rows."""

import csv
import os
from pathlib import Path as FilePath

from cascade_cms.cmstypes import (
    IdentifierType,
    NewAsset,
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

CSV_PATH: FilePath = FilePath(
    "./assets.csv"
)  # columns: name,title,folder
SITE_NAME: str = "www"


def build_payloads() -> list[NewAsset]:
    payloads = []
    with CSV_PATH.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            payloads.append(
                NewAsset(
                    name=row["name"],
                    asset_type="page",
                    # Exactly one of site_name/site_id and
                    # exactly one of parent_folder_path/
                    # parent_folder_id — both-or-neither
                    # fails.
                    site_name=SITE_NAME,
                    parent_folder_path=row["folder"],
                    # extra="allow": type-specific fields
                    # pass straight through.
                    title=row["title"],
                )
            )
    return payloads


def main() -> None:
    payloads = build_payloads()
    if not payloads:
        print(f"No rows in {CSV_PATH}.")
        return

    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        # One create() per payload: each becomes its own
        # chain, so .success / .failed are per asset. A
        # single create(payloads) list is ONE chain whose
        # result is a list.
        for payload in payloads:
            cascade.operations.create(payload)

        results = cascade.submit_requests(IdentifierType)

        created = 0
        for result in results.success:
            created += 1
            kind, new_id = (
                result.get_type,
                result.get_id,
            )
            print(f"Created {kind} {new_id}")
        print(f"{created}/{len(payloads)} created.")


if __name__ == "__main__":
    main()

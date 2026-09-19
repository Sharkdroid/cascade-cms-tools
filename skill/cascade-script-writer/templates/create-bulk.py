#!/usr/bin/env python3
"""Create many assets in one batch from CSV rows."""

import csv
import os
from pathlib import Path as FilePath
from typing import Any

from cascade_cms.cmstypes import (
    CascadeError,
    IdentifierType,
    NewAsset,
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
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.create(payloads)

        try:
            results = cascade.submit_requests(
                IdentifierType
            )
        except Exception as exc:
            print(f"Request submission failed: {exc}")
            return

        created = 0
        for result in results:
            if isinstance(result, CascadeError):
                print(f"FAILED: {result.message}")
            else:
                created += 1
                kind, new_id = (
                    result.get_type,
                    result.get_id,
                )
                print(f"Created {kind} {new_id}")
        print(f"{created}/{len(payloads)} created.")


if __name__ == "__main__":
    main()

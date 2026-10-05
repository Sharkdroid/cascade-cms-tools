#!/usr/bin/env python3
"""Create many assets in one batch from any row source.

`create` needs no earlier step: only a NewAsset that passes
its own validation. Every NewAsset is built BEFORE the
wrapper opens, so bad rows are reported together and no
request is sent. If a create needs data from Cascade (a
data definition, say), fetch it in an earlier phase (see
read-graph), then build the NewAsset.

Failures map back to input rows via the FULL results list
and `results.failed` (`chain_index` is 1-based per batch).
Never zip `results.success` against your inputs.
"""

import os

from cascade_cms.cmstypes import (
    IdentifierType,
    NewAsset,
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

# Placeholder: rows can come from anywhere (CSV, JSON, a
# database, an API). Swap this one list for your source.
ROWS: list[dict[str, str]] = [
    {"name": "about", "title": "About", "folder": "/"},
    {"name": "news", "title": "News", "folder": "/"},
]


def build_payloads(
    rows: list[dict[str, str]],
) -> tuple[list[NewAsset], list[str]]:
    """Pure: no I/O. Returns payloads and row errors."""
    payloads: list[NewAsset] = []
    errors: list[str] = []
    for index, row in enumerate(rows):
        try:
            payloads.append(
                NewAsset(
                    name=row["name"],
                    asset_type="page",
                    # Exactly one of site_name/site_id and
                    # exactly one of parent_folder_path/
                    # parent_folder_id.
                    site_name=SITE_NAME,
                    parent_folder_path=row["folder"],
                    # extra="allow": extra fields pass
                    # through at the path given. Confirm
                    # each one live (SKILL.md Step 3):
                    # title lives under metadata.
                    metadata={"title": row["title"]},
                )
            )
        except (KeyError, ValueError) as err:
            errors.append(f"row {index} invalid: {err}")
    return payloads, errors


def main() -> None:
    payloads, errors = build_payloads(ROWS)
    if errors:
        for message in errors:
            print(message)
        return
    if not payloads:
        print("No rows.")
        return

    with Cascade(environment_variables) as cascade:
        # One create() per payload: each becomes its own
        # chain. A single create(payloads) list is ONE
        # chain whose result is a list.
        for payload in payloads:
            cascade.operations.create(payload)

        results = cascade.submit_requests(IdentifierType)

        # chain_index is 1-based within this batch.
        for failure in results.failed:
            row = failure.chain_index - 1
            print(f"row {row} failed: {failure.message}")
        created = len(payloads) - len(results.failed)
        print(f"{created}/{len(payloads)} created.")


if __name__ == "__main__":
    main()

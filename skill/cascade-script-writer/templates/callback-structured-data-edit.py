#!/usr/bin/env python3
"""Edit one structured-data field, safely.

- Address one group and one field; never the whole
  structure (no get/print/return/assign of
  structuredData).
- Names come from live data. If the Cascade MCP is
  connected, confirm them with
  cascade_get_data_structure; else ask the user.
- A None or wrong count RAISES: a typo would otherwise
  edit nothing and still report success.
- Group identifiers can repeat and nest. direct=True
  reads only the group's own fields, never a same-
  named field in a nested group. Every instance of
  the group is edited.
- If the group identifier repeats under different
  parents, pass a tuple path ending at the group,
  e.g. ("page-section", "column").
- A raise here is logged as [CASCADE-REST-CMS]
  (LIBRARY) with your message after "ValueError:".
  The prefix does not mean a library bug.
- Writes are delivered in stages (SKILL.md Step 6).
  Confirm the node's live shape first.

Cascade type-checks none of these fields: a wrong
string is stored, then breaks or misleads the editor.
So the value is BUILT by an encoder that raises on
anything invalid, never typed by hand. Set FIELD_KIND
to the field's schema type (cascade_get_data_structure
with node_identifier):

- text: free text (schema type null). A str.
- radio: a str that must be in ALLOWED_OPTIONS, the
  schema's radio-item values.
- multiselect: a list[str], every item in
  ALLOWED_OPTIONS. Stored as ::CONTENT-XML-SELECTOR::
  before each item; [] is the bare marker.
- checkbox: like multiselect with the marker
  ::CONTENT-XML-CHECKBOX:: (from a production script,
  not live-tested here; read back to confirm).
- calendar: a date, stored MM-DD-YYYY.
- datetime: a timezone-aware datetime, stored as Unix
  epoch MILLISECONDS. Not the ISO 8601 that asset
  dates such as lastModifiedDate use.

To clear a calendar or datetime field set NEW_VALUE to
None: the "text" key is removed, the node stays.

Chooser (asset) nodes are not covered here: see
SKILL.md, "File choosers".

get_data_structure(group, identifier, direct=True)
returns matching nodes BY REFERENCE, so setting
node["text"] edits the asset itself. One chain per
target:
`read(identifier).edit(update_node)`.
"""

import os
import uuid
from datetime import date, datetime

from cascade_cms.cmstypes import (
    Asset,
    CascadeSuccess,
    IdentifierType,
)
from cascade_cms.utils import script_log
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

# A group identifier (a str is always ONE identifier,
# dots allowed), or a tuple path ending at the group
# you mean, e.g. ("page-section", "column").
GROUP: str | tuple[str, ...] = "contact-block"
FIELD: str = "phone"
FIELD_KIND: str = "text"
ALLOWED_OPTIONS: list[str] = []
NEW_VALUE: str | list[str] | date | datetime | None = (
    "+1 555 0100"
)
EXPECTED_COUNT: int = 1

SELECTOR_MARKER: str = "::CONTENT-XML-SELECTOR::"
CHECKBOX_MARKER: str = "::CONTENT-XML-CHECKBOX::"


def encode_options(
    marker: str, value: object, allowed: list[str]
) -> str:
    """Marker before every option; [] is the bare marker."""
    if not isinstance(value, list):
        raise ValueError("expected a list of options")
    if not allowed:
        raise ValueError(
            "set ALLOWED_OPTIONS from the schema"
        )
    for item in value:
        if not isinstance(item, str) or item not in allowed:
            raise ValueError(
                f"{item!r} is not one of the schema options"
            )
    if len(set(value)) != len(value):
        raise ValueError("duplicate option")
    return marker + marker.join(value) if value else marker


def encode_value(
    kind: str, value: object, allowed: list[str]
) -> str | None:
    """Build the exact string Cascade stores, or raise.

    None (calendar and datetime only) means clear: the
    caller removes the node's "text" key.
    """
    if value is None and kind in ("calendar", "datetime"):
        return None
    if kind == "text":
        if not isinstance(value, str):
            raise ValueError("text needs a str")
        return value
    if kind == "radio":
        if (
            not isinstance(value, str)
            or value not in allowed
        ):
            raise ValueError(
                f"{value!r} is not a radio-item value"
            )
        return value
    if kind == "multiselect":
        return encode_options(
            SELECTOR_MARKER, value, allowed
        )
    if kind == "checkbox":
        return encode_options(
            CHECKBOX_MARKER, value, allowed
        )
    if kind == "calendar":
        if not isinstance(value, date) or isinstance(
            value, datetime
        ):
            raise ValueError("calendar needs a date")
        return value.strftime("%m-%d-%Y")
    if kind == "datetime":
        if not isinstance(value, datetime):
            raise ValueError("datetime needs a datetime")
        if value.tzinfo is None:
            raise ValueError("datetime must be tz-aware")
        return str(int(value.timestamp() * 1000))
    raise ValueError(f"unknown FIELD_KIND {kind!r}")


def update_node(asset: Asset) -> Asset:
    text = encode_value(
        FIELD_KIND, NEW_VALUE, ALLOWED_OPTIONS
    )
    group_label = (
        GROUP if isinstance(GROUP, str) else "/".join(GROUP)
    )
    # Only GROUP's own fields; never a same-named field
    # in a nested group.
    nodes = asset.get_data_structure(
        GROUP, FIELD, direct=True
    )
    if not nodes:
        raise ValueError(f"no {group_label}/{FIELD} node")
    if len(nodes) != EXPECTED_COUNT:
        raise ValueError(
            f"expected {EXPECTED_COUNT} node(s), "
            f"found {len(nodes)}"
        )
    # Count only; never log the values.
    script_log.note(
        f"set {group_label}/{FIELD} ({FIELD_KIND}) on "
        f"{asset.get('id')}: {len(nodes)} node(s)"
    )
    for node in nodes:
        # By reference: this edits the asset in place.
        if text is None:
            node.pop("text", None)
        else:
            node["text"] = text
    return asset


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        for identifier in TARGETS:
            cascade.operations.read(identifier).edit(
                update_node
            )

        results = cascade.submit_requests(CascadeSuccess)

        print(f"Saved {len(results.success)}.")
        for failure in results.failed:
            print(
                f"failed: {failure.identifier}: "
                f"{failure.message}"
            )


if __name__ == "__main__":
    main()

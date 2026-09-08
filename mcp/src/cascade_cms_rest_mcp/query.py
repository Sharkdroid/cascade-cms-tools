"""Parse and evaluate a small, safe path-query language over arbitrary
Cascade asset JSON (`asset._data`), so an agent can narrow a read to one
sub-value instead of collapsing/dumping the whole payload.

Query strings look like a Python expression - `metadata.dynamicFields[0].value`,
`metadata["dynamicFields"][0]`, `metadata["*"]`, `find("identifier")` - but are
never `eval`'d. `ast.parse(..., mode="eval")` builds a real AST, which is then
walked by a tiny whitelist that only understands attribute/subscript chains,
int/str/negative-int constants, and one specific `find(...)` call shape.
Anything else (arbitrary calls, binary ops, comparisons, lambdas, ...) is
rejected before any traversal of the asset data happens - this boundary
matters because the query string is untrusted agent input, not just a UX nicety.

This mirrors data_structure.py's recursive-descent style (find_group/find_node)
but generalizes it over plain JSON dict/list data of any shape, rather than the
XML-derived data-definition tree, since Cascade asset payloads vary per asset
type (Asset.__init__ in cmstypes.py treats `_data` as a schema-less dict).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, NamedTuple


class QueryError(Exception):
    """Raised for a query string that can't be parsed/whitelisted. Callers
    (server.py) translate this into a self-correcting ToolError via
    errors.invalid_query_error."""


@dataclass(frozen=True)
class Key:
    name: str


@dataclass(frozen=True)
class Index:
    value: int


@dataclass(frozen=True)
class Wildcard:
    pass


@dataclass(frozen=True)
class Find:
    name: str


Step = Key | Index | Wildcard | Find


class Match(NamedTuple):
    path: str
    value: Any


def parse_query(query: str) -> list[Step]:
    """Parse a query string into a list of Steps. An empty/whitespace-only
    query means "the whole asset" (no steps, root value only)."""
    text = query.strip()
    if not text:
        return []
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise QueryError(f"not a valid query expression: {exc.msg}") from exc
    return _walk(tree.body)


def _walk(node: ast.expr) -> list[Step]:
    if isinstance(node, ast.Name):
        # There is no separate "root" token in this grammar - a bare leading
        # identifier (e.g. "metadata" in "metadata.title") IS the first key
        # step into the asset data, exactly like an attribute/subscript
        # further down the chain.
        return [Key(node.id)]

    if isinstance(node, ast.Attribute):
        return [*_walk(node.value), Key(node.attr)]

    if isinstance(node, ast.Subscript):
        base = _walk(node.value)
        index = _walk_index(node.slice)
        return [*base, index]

    if isinstance(node, ast.Call):
        return _walk_find_call(node)

    raise QueryError(
        f"unsupported query syntax ({type(node).__name__}). Only dotted/bracket "
        'field access (a.b, a["b"], a[0]), "*" wildcards, and find("key") are '
        "supported."
    )


def _walk_index(slice_node: ast.expr) -> Step:
    if isinstance(slice_node, ast.Constant):
        value = slice_node.value
        if isinstance(value, str):
            return Wildcard() if value == "*" else Key(value)
        if isinstance(value, bool):
            raise QueryError("boolean index is not a valid query step")
        if isinstance(value, int):
            return Index(value)
        raise QueryError(f"unsupported index constant: {value!r}")

    if (
        isinstance(slice_node, ast.UnaryOp)
        and isinstance(slice_node.op, ast.USub)
        and isinstance(slice_node.operand, ast.Constant)
        and isinstance(slice_node.operand.value, int)
        and not isinstance(slice_node.operand.value, bool)
    ):
        return Index(-slice_node.operand.value)

    raise QueryError(
        f"unsupported index expression ({type(slice_node).__name__}); use a "
        'string key, an integer index, or "*"'
    )


def _walk_find_call(node: ast.Call) -> list[Step]:
    if isinstance(node.func, ast.Name) and node.func.id == "find":
        base: list[Step] = []
    elif isinstance(node.func, ast.Attribute) and node.func.attr == "find":
        base = _walk(node.func.value)
    else:
        raise QueryError(
            "the only supported function call is find(\"key\"), optionally "
            'chained after a path, e.g. metadata.find("identifier")'
        )
    if node.keywords or len(node.args) != 1:
        raise QueryError('find(...) takes exactly one positional string argument')
    arg = node.args[0]
    if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
        raise QueryError('find(...) argument must be a string literal, e.g. find("identifier")')
    return [*base, Find(arg.value)]


def _format_path(parts: tuple[str, ...]) -> str:
    path = "$"
    for part in parts:
        path += part if part.startswith("[") else f".{part}"
    return path


def _find_all(
    path: tuple[str, ...], value: Any, name: str
) -> list[tuple[tuple[str, ...], Any]]:
    matches: list[tuple[tuple[str, ...], Any]] = []
    if isinstance(value, dict):
        for key, sub_value in value.items():
            sub_path = (*path, key)
            if key == name:
                matches.append((sub_path, sub_value))
            matches.extend(_find_all(sub_path, sub_value, name))
    elif isinstance(value, list):
        for i, sub_value in enumerate(value):
            matches.extend(_find_all((*path, f"[{i}]"), sub_value, name))
    return matches


def evaluate(data: Any, steps: list[Step]) -> list[Match]:
    """Apply `steps` to `data`, starting at the root. A plain key/index chain
    with no Wildcard/Find yields at most one match (zero if the path doesn't
    exist - a miss, not an error, mirroring data_structure.find_group/find_node
    returning None). Wildcard/Find steps can fan out to many matches."""
    current: list[tuple[tuple[str, ...], Any]] = [((), data)]
    for step in steps:
        next_current: list[tuple[tuple[str, ...], Any]] = []
        for path, value in current:
            if isinstance(step, Key):
                if isinstance(value, dict) and step.name in value:
                    next_current.append(((*path, step.name), value[step.name]))
            elif isinstance(step, Index):
                if isinstance(value, list) and -len(value) <= step.value < len(value):
                    next_current.append(((*path, f"[{step.value}]"), value[step.value]))
            elif isinstance(step, Wildcard):
                if isinstance(value, list):
                    next_current.extend(
                        ((*path, f"[{i}]"), item) for i, item in enumerate(value)
                    )
                elif isinstance(value, dict):
                    next_current.extend(
                        ((*path, key), item) for key, item in value.items()
                    )
            elif isinstance(step, Find):
                next_current.extend(_find_all(path, value, step.name))
        current = next_current
    return [Match(_format_path(path), value) for path, value in current]

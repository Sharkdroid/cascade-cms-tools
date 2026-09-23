#!/usr/bin/env python3
"""Static validator for generated cascade_cms scripts.

Checks, each gating the next:
  0. Bundle banner      - prints the bundled library version + manifest status,
                          so a stale snapshot is never silent.
  1. Syntax             - ast.parse(); catches typos, indentation, brackets.
  2. Wrapper-only       - fails on cascade_cms.driver usage, manual asyncio
                          event-loop management, or a hand-built ClientSession.
  3. Imports            - imports the real bundled package and verifies every
                          name the script imports actually exists.
  4. Operation names    - flags cascade.operations.<X> where X is not a real
                          Operations method, suggesting the closest match.
  5. Asset writes       - flags asset[...] = ... on an Asset; Asset defines
                          __setattr__, not __setitem__.
  6. Path identifiers   - flags Path dict literals missing siteName/asset_type.
  7. Result type        - warns when submit_requests(T) disagrees with the
                          queued operation's actual return type.
  8. Construction       - re-instantiates every payload model call found in the
                          script against the real Pydantic models.
  9. Type hints         - every def needs annotated params and a return type,
                          and every module-level variable needs an annotation.
 10. Line length        - no line over 60 chars (code, comments, docstrings);
                          also `ruff format --check --line-length 60` if ruff
                          is available.
 11. Deprecated get()   - warns on asset.get("structuredData...") and
                          asset.get("pageConfigurations..."): cascade-cms-rest
                          3.1.6 warns there and points to the designated
                          accessors.

Usage:
    python validate_script.py path/to/generated_script.py

Exit code 0 = all checks passed. Non-zero = see output for details.
No network calls are made at any point.
"""

import ast
import difflib
import json
import shutil
import subprocess
import sys
from pathlib import Path

MAX_LINE_LENGTH = 60

SKILL_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_PKG_PARENT = SKILL_ROOT
MANIFEST_PATH = SKILL_ROOT / "cascade_cms" / "_bundle_manifest.json"


def field_reference() -> str:
    """Name the field reference this bundle ships, so error messages never
    point a model at a file that isn't there."""
    if (SKILL_ROOT / "references/operations_schema.json").exists():
        return "references/operations_schema.json"
    return "the bundled reference files"


def print_bundle_banner() -> None:
    """Level 0: surface which library version this validator actually checks
    against. Silent drift between the bundle and src/cascade_cms/ is what made
    the previous skill reject correct scripts."""
    if not MANIFEST_PATH.exists():
        print("[BUNDLE] WARNING: no _bundle_manifest.json — snapshot provenance unknown.")
        print("         Run: python build_release.py")
        return
    try:
        manifest = json.loads(MANIFEST_PATH.read_text())
    except json.JSONDecodeError as e:
        print(f"[BUNDLE] WARNING: manifest unreadable ({e}).")
        return

    version = manifest.get("library_version", "unknown")
    print(f"[BUNDLE] Validating against cascade-cms-rest {version}")

    import hashlib

    drifted = [
        name
        for name, digest in manifest.get("files", {}).items()
        if not (SKILL_ROOT / "cascade_cms" / name).exists()
        or hashlib.sha256((SKILL_ROOT / "cascade_cms" / name).read_bytes()).hexdigest()
        != digest
    ]
    if drifted:
        print(f"[BUNDLE] WARNING: {len(drifted)} bundled file(s) differ from the manifest:")
        for name in drifted:
            print(f"           - {name}")
        print("         Rebuild with: python build_release.py")


def check_syntax(source: str, path: str) -> ast.Module:
    """Level 1: parse the file. Raises SyntaxError with line info on failure."""
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as e:
        print(f"[SYNTAX ERROR] {path}:{e.lineno}:{e.offset}: {e.msg}")
        sys.exit(1)
    print("[OK] Syntax check passed")
    return tree


FORBIDDEN_DRIVER_NAMES = {
    "CascadeCMSRestDriver",
    "RequestExecutor",
    "CacheHandler",
    "DEFAULT_CACHECONFIG",
}

# Attribute/call names indicating manual loop/session management. Checked as
# the called attribute name rather than a specific import alias, so this still
# catches `import asyncio as aio; aio.new_event_loop()`.
FORBIDDEN_LOOP_SESSION_CALLS = {
    "new_event_loop": "creates a raw event loop — CascadeWrapperBase owns the loop for the session's lifetime",
    "set_event_loop": "reassigns the running event loop — CascadeWrapperBase already does this internally",
    "run_until_complete": "drives the loop manually — use cascade.submit_requests() instead",
    "get_event_loop": "reaches for the loop directly — not needed outside the wrapper",
}
FORBIDDEN_SESSION_CONSTRUCTORS = {"ClientSession"}


def check_wrapper_only(tree: ast.Module, path: str):
    """Level 2: fail if the script touches cascade_cms.driver directly, OR
    manually manages an event loop / HTTP session. CascadeWrapperBase must be
    the sole entry point — any of these bypass logger wiring, the callback
    execution path, and session/event-loop cleanup."""
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "cascade_cms.driver" or node.module.endswith(".driver"):
                names = ", ".join(a.name for a in node.names)
                violations.append(
                    f"line {node.lineno}: 'from {node.module} import {names}' — "
                    f"import from cascade_cms.wrapper instead"
                )
            else:
                for alias in node.names:
                    if alias.name in FORBIDDEN_DRIVER_NAMES:
                        violations.append(
                            f"line {node.lineno}: imports '{alias.name}' directly — "
                            f"driver internals must not be used outside CascadeWrapperBase"
                        )
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cascade_cms.driver" or alias.name.endswith(".driver"):
                    violations.append(
                        f"line {node.lineno}: 'import {alias.name}' — "
                        f"scripts must not import the driver module"
                    )
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_DRIVER_NAMES:
            violations.append(f"line {node.lineno}: references '{node.id}' directly")
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_DRIVER_NAMES:
            violations.append(f"line {node.lineno}: references '.{node.attr}' directly")

        if isinstance(node, ast.Call):
            called_name = None
            if isinstance(node.func, ast.Attribute):
                called_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                called_name = node.func.id
            if called_name in FORBIDDEN_LOOP_SESSION_CALLS:
                reason = FORBIDDEN_LOOP_SESSION_CALLS[called_name]
                violations.append(f"line {node.lineno}: calls '{called_name}()' — {reason}")
            if called_name in FORBIDDEN_SESSION_CONSTRUCTORS:
                violations.append(
                    f"line {node.lineno}: constructs '{called_name}(...)' directly — "
                    f"CascadeWrapperBase/driver owns the HTTP session; scripts should never open their own"
                )

    if violations:
        print("[WRAPPER-ONLY ERROR] Script bypasses CascadeWrapperBase:")
        for v in sorted(set(violations)):
            print(f"  - {v}")
        print("  Fix: use only CascadeWrapperBase + cascade.operations.<op>(...) + cascade.submit_requests(...)")
        sys.exit(1)
    print("[OK] Wrapper-only check passed — no direct driver usage")


def _load_modules():
    sys.path.insert(0, str(BUNDLED_PKG_PARENT))
    try:
        import cascade_cms.cmstypes as cmstypes
        import cascade_cms.driver as driver
        import cascade_cms.failures as failures
        import cascade_cms.operations as operations
        import cascade_cms.wrapper as wrapper
    except Exception as e:
        print(f"[IMPORT ERROR] Could not import bundled cascade_cms package: {e}")
        sys.exit(1)
    return {
        "cascade_cms.cmstypes": cmstypes,
        "cascade_cms.operations": operations,
        "cascade_cms.wrapper": wrapper,
        "cascade_cms.driver": driver,
        "cascade_cms.failures": failures,
    }


def check_imports(tree: ast.Module, source_path: str):
    """Level 3: import cascade_cms for real and verify every name the script
    imports from it actually exists (catches renamed/misspelled symbols)."""
    modules = _load_modules()

    missing = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("cascade_cms"):
            mod = modules.get(node.module)
            if mod is None:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                if not hasattr(mod, alias.name):
                    candidates = difflib.get_close_matches(
                        alias.name, [n for n in dir(mod) if not n.startswith("_")], n=3
                    )
                    hint = f" Did you mean: {', '.join(candidates)}?" if candidates else ""
                    missing.append(f"{node.module}.{alias.name} (line {node.lineno}).{hint}")

    if missing:
        print("[IMPORT ERROR] The following imported names do not exist in cascade_cms:")
        for m in missing:
            print(f"  - {m}")
        print("  Fix: correct the name, or read cascade_cms/cmstypes.py for the real symbol.")
        sys.exit(1)
    print("[OK] Import check passed — all cascade_cms references are real")


def check_operation_names(tree: ast.Module):
    """Level 4: flag cascade.operations.<X>(...) where X is not a real
    Operations method. A typo here otherwise fails only at runtime, after
    the script has already authenticated against a live server."""
    modules = _load_modules()
    operations_cls = modules["cascade_cms.operations"].Operations
    valid = {n for n in dir(operations_cls) if not n.startswith("_")}

    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        inner = node.func.value
        # match `<anything>.operations.<method>(...)`
        if isinstance(inner, ast.Attribute) and inner.attr == "operations":
            name = node.func.attr
            if name not in valid:
                candidates = difflib.get_close_matches(name, sorted(valid), n=3)
                hint = (
                    f" Did you mean: {', '.join(candidates)}?"
                    if candidates
                    else f" Valid operations: {', '.join(sorted(valid))}"
                )
                bad.append(f"line {node.lineno}: cascade.operations.{name}(...) does not exist.{hint}")

    if bad:
        print("[OPERATION ERROR] Unknown Operations method(s):")
        for b in bad:
            print(f"  - {b}")
        sys.exit(1)
    print("[OK] Operation-name check passed")


def check_asset_subscript_assignment(tree: ast.Module):
    """Level 5: flag `asset[...] = ...` where the target is an Asset.

    Asset is dict-*backed* but not dict-*like* for writes: it defines
    __setattr__ and .get(), and no __setitem__ at all, so subscript assignment
    raises TypeError at runtime. Published wiki examples get this wrong.
    """
    asset_names = set()

    for node in ast.walk(tree):
        # def cb(asset: Asset) / def cb(a: "Asset")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in list(node.args.args) + list(node.args.kwonlyargs):
                ann = arg.annotation
                if isinstance(ann, ast.Name) and ann.id == "Asset":
                    asset_names.add(arg.arg)
                elif isinstance(ann, ast.Constant) and ann.value == "Asset":
                    asset_names.add(arg.arg)
        # x: Asset = ...
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            ann = node.annotation
            if (isinstance(ann, ast.Name) and ann.id == "Asset") or (
                isinstance(ann, ast.Constant) and ann.value == "Asset"
            ):
                asset_names.add(node.target.id)
        # x = Asset(...)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Name) and func.id == "Asset":
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        asset_names.add(target.id)
        # for asset in <...>: with isinstance(x, Asset) guard is not tracked —
        # annotation-based detection only, to avoid false positives on dicts.

    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id in asset_names
            ):
                key = ""
                if isinstance(target.slice, ast.Constant):
                    key = str(target.slice.value)
                var = target.value.id
                suggestion = f"{var}.{key} = ..." if key.isidentifier() else f"{var}.<field> = ..."
                violations.append(
                    f"line {node.lineno}: `{var}[{key!r}] = ...` — `Asset` has no `__setitem__`. "
                    f"Use `{suggestion}` instead (Asset defines __setattr__, not __setitem__)."
                )

    if violations:
        print("[ASSET WRITE ERROR] Subscript assignment on an Asset:")
        for v in violations:
            print(f"  - {v}")
        print(
            "  Read with asset.get('field') (dotted paths like "
            "'metadata.dynamicFields' work); write with "
            "asset.field = value."
        )
        sys.exit(1)
    print("[OK] Asset write check passed")


IDENTIFIER_OP_NAMES = {
    "read", "delete", "copy", "move", "publish", "checkIn", "checkOut",
    "listSubscribers", "readAccessRights", "readWorkflowSettings",
    "readWorkflowInformation", "performWorkflowTransition",
}


def _dict_literal_keys(node: ast.Dict) -> set[str]:
    return {k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}


def check_path_identifiers(tree: ast.Module):
    """Level 6: `Path` is a Pydantic model (3.2.2+), not a dict. A dict
    literal passed as an identifier crashes in resolve_identifier() (it reads
    `.site_name` by attribute), and a `Path(...)` without a site name raises
    ValueError at request-build time. Catch both statically."""
    violations = []

    def inspect_dict(d: ast.Dict, lineno: int, where: str):
        keys = _dict_literal_keys(d)
        if "path" in keys:
            violations.append(
                f"line {lineno}: {where} uses a dict literal as a Path. Path is a "
                f"Pydantic model since cascade-cms-rest 3.2.2 — write "
                f"Path(site_name=..., path=..., asset_type=...) instead."
            )

    def inspect_call(call: ast.Call):
        names = {kw.arg for kw in call.keywords}
        if None in names:
            return  # **kwargs: cannot tell statically
        if not ({"site_name", "siteName"} & names):
            violations.append(
                f"line {call.lineno}: Path(...) has no site_name — "
                f"resolve_identifier() raises ValueError('Path identifiers require "
                f"site_name to build the request URL'). Add site_name='<site>'."
            )
        if "asset_type" not in names:
            violations.append(
                f"line {call.lineno}: Path(...) is missing asset_type (e.g. 'page', "
                f"'file', 'folder') — required to build the request URL."
            )

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Path"
        ):
            inspect_call(node)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr not in IDENTIFIER_OP_NAMES:
                continue
            where = f"operations.{node.func.attr}(...)"
            for arg in node.args[:1]:
                elts = arg.elts if isinstance(arg, ast.List | ast.Tuple) else [arg]
                for elt in elts:
                    if isinstance(elt, ast.Dict):
                        inspect_dict(elt, node.lineno, where)
        # standalone `ident: Path = {...}`
        if isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Dict):
            ann = node.annotation
            if isinstance(ann, ast.Name) and ann.id == "Path":
                inspect_dict(node.value, node.lineno, "Path annotation")

    if violations:
        print("[PATH IDENTIFIER ERROR] Malformed Path identifier(s):")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    print("[OK] Path identifier check passed")


def check_chain_results_attrs(tree: ast.Module) -> None:
    """Level 6b: `ChainResults` exposes `.success` and `.failed`. `.ok` was
    renamed to `.success` in cascade-cms-rest 3.2.2 with no alias, so it
    raises AttributeError at runtime; catch it on anything bound directly
    from submit_requests()."""

    def is_submit(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "submit_requests"
        )

    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign | ast.AnnAssign) and node.value is not None:
            if is_submit(node.value):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                bound.update(t.id for t in targets if isinstance(t, ast.Name))

    errors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "ok":
            value = node.value
            if is_submit(value) or (isinstance(value, ast.Name) and value.id in bound):
                errors.append(f"line {node.lineno}")
    if errors:
        print(
            "[RESULTS ERROR] `.ok` on a submit_requests() result: "
            + ", ".join(errors)
        )
        print("  Fix: ChainResults.ok was renamed to .success (no alias).")
        sys.exit(1)
    print("[OK] ChainResults attribute check passed")


# What each operation actually resolves to once parsed.
OPERATION_RESULT_TYPES = {
    "read": "Asset",
    "create": "IdentifierType",
    "edit": "CascadeSuccess",
    "delete": "CascadeSuccess",
    "copy": "CascadeSuccess",
    "move": "CascadeSuccess",
    "publish": "CascadeSuccess",
    "siteCopy": "CascadeSuccess",
    "checkIn": "CascadeSuccess",
    "checkOut": "CheckedOutAsset",
    "editAccessRights": "CascadeSuccess",
    "editWorkflowSettings": "CascadeSuccess",
    "editPreference": "CascadeSuccess",
    "markMessage": "CascadeSuccess",
    "deleteMessage": "CascadeSuccess",
    "performWorkflowTransition": "CascadeSuccess",
    "search": "ListElements",
    "listSites": "ListElements",
    "listMessages": "ListElements",
    "listSubscribers": "ListElements",
    "readAudits": "ListElements",
    "readAccessRights": "accessRightsInformationPayload",
    "readWorkflowSettings": "workflowSettingsPayload",
    "readWorkflowInformation": "workflowInformation",
    "readPreferences": "SimplePayload",
}


def _callback_returns(tree: ast.Module) -> dict[str, str | None]:
    """Map each def's name to its return annotation (None if absent)."""
    out: dict[str, str | None] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            out[node.name] = ast.unparse(node.returns) if node.returns else None
    return out


def _chain_links(call: ast.Call) -> list[ast.Call] | None:
    """Unwind `x.operations.a(...).then(...).b(...)` into its calls, in
    order. None when the expression is not rooted at `.operations`."""
    links: list[ast.Call] = []
    node: ast.expr = call
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        links.append(node)
        node = node.func.value
    if isinstance(node, ast.Attribute) and node.attr == "operations":
        return list(reversed(links))
    return None


def _chain_result_type(links: list[ast.Call], returns: dict[str, str | None]) -> str | None:
    """The type the chain's last node yields, or None when unknown.

    A callback annotated `-> None` passes the previous result through (the
    library treats a None return as a side effect); any other annotation
    becomes the chain's type. An unannotated or unresolvable callback makes
    the type unknown, so no warning is raised for it.
    """
    current: str | None = None
    for link in links:
        assert isinstance(link.func, ast.Attribute)
        name = link.func.attr
        if name == "then":
            fns: list[ast.expr] = []
            for arg in link.args:
                fns.extend(arg.elts if isinstance(arg, ast.List) else [arg])
            for fn in fns:
                if not isinstance(fn, ast.Name) or fn.id not in returns:
                    return None
                annotation = returns[fn.id]
                if annotation is None:
                    return None
                if annotation != "None":
                    current = annotation
        elif name in OPERATION_RESULT_TYPES:
            current = OPERATION_RESULT_TYPES[name]
        else:
            return None
    return current


def check_result_type(tree: ast.Module):
    """Level 7: warn when submit_requests(T) disagrees with what the chains
    queued in THAT batch actually yield — the last operation's type, or the
    return annotation of a trailing `.then()` callback. Batches are split
    at each submit_requests() call, in source order within a function.
    This is a type-hint-only argument, so a mismatch never fails at
    runtime — it just makes the script lie to its reader and to mypy."""
    returns = _callback_returns(tree)
    warnings = []
    scopes = [tree] + [
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    for scope in scopes:
        events: list[tuple[int, int, str, ast.Call]] = []
        for node in ast.walk(scope):
            if node is not scope and isinstance(
                node, ast.FunctionDef | ast.AsyncFunctionDef
            ):
                continue
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr == "submit_requests":
                events.append((node.lineno, node.col_offset, "submit", node))
            elif _chain_links(node) is not None:
                events.append((node.lineno, node.col_offset, "chain", node))
        # Keep only outermost chain calls: an inner link of a chain is
        # itself rooted at .operations and would be counted twice.
        inner = {
            id(link)
            for _, _, kind, call in events if kind == "chain"
            for link in (_chain_links(call) or [])[:-1]
        }
        batch: set[str | None] = set()
        for lineno, _, kind, call in sorted(events, key=lambda e: e[:2]):
            if kind == "chain":
                if id(call) in inner:
                    continue
                links = _chain_links(call) or []
                batch.add(_chain_result_type(links, returns))
                continue
            if (
                call.args
                and isinstance(call.args[0], ast.Name)
                and batch
                and None not in batch
            ):
                hinted = call.args[0].id
                known = sorted(t for t in batch if t is not None)
                if hinted not in known:
                    warnings.append(
                        f"line {lineno}: submit_requests({hinted}) but this "
                        f"batch's chains yield {' | '.join(known)}. "
                        f"Use submit_requests({known[0]}) or drop the hint."
                    )
            batch = set()

    for w in sorted(set(warnings)):
        print(f"[WARN] {w}")
    print("[OK] Result-type check passed" + (" (with warnings)" if warnings else ""))


CONSTRUCTIBLE_NAMES = {
    "NewAsset", "IdentifierType", "deleteParameters", "copyParameters",
    "moveParameters", "publishInformation", "Comment", "SiteCopyParameter",
    "workflowTransitionInformation", "auditParameters", "SearchInformation",
    "preference", "Message", "accessRightsInformationPayload",
    "workflowSettingsPayload", "Path", "PathBase",
}


def check_construction(tree: ast.Module, source: str):
    """Level 8: find calls to known Pydantic payload/model classes and
    re-instantiate them with the literal args used in the script, so validation
    errors (missing required field, bad alias, wrong type) surface now instead
    of at runtime against a live Cascade server."""
    sys.path.insert(0, str(BUNDLED_PKG_PARENT))
    import cascade_cms.cmstypes as cmstypes

    constructible = {
        name: obj
        for name, obj in vars(cmstypes).items()
        if isinstance(obj, type) and name in CONSTRUCTIBLE_NAMES
    }

    errors = []
    checked = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            cls_name = node.func.id
            if cls_name not in constructible:
                continue
            try:
                kwargs = {}
                skip = False
                for kw in node.keywords:
                    if kw.arg is None:
                        skip = True
                        break
                    try:
                        kwargs[kw.arg] = ast.literal_eval(kw.value)
                    except (ValueError, SyntaxError):
                        skip = True
                        break
                if skip or not kwargs:
                    continue
                checked += 1
                constructible[cls_name](**kwargs)
            except Exception as e:
                errors.append(f"{cls_name}(...) at line {node.lineno}: {e}")

    if errors:
        print(f"[CONSTRUCTION ERROR] {len(errors)} payload construction(s) failed validation:")
        for err in errors:
            print(f"  - {err}")
        print(f"  Fix: check field names and aliases in {field_reference()}.")
        sys.exit(1)
    print(f"[OK] Construction check passed — {checked} payload instantiation(s) validated")


def _unannotated_params(node: ast.FunctionDef | ast.AsyncFunctionDef, in_class: bool) -> list[str]:
    """Names of parameters on `node` that have no annotation. The first
    parameter of a method (self/cls) is exempt."""
    args = node.args
    positional = list(args.posonlyargs) + list(args.args)
    if in_class and positional and positional[0].arg in ("self", "cls"):
        positional = positional[1:]
    params = positional + list(args.kwonlyargs)
    if args.vararg:
        params.append(args.vararg)
    if args.kwarg:
        params.append(args.kwarg)
    return [a.arg for a in params if a.annotation is None]


def check_type_hints(tree: ast.Module) -> None:
    """Level 9: every function parameter and return, and every
    module-level variable, must be type-hinted. Callbacks and nested
    functions included; lambdas cannot be annotated and are exempt."""
    violations: list[str] = []

    class_methods: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    class_methods.add(id(item))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        missing = _unannotated_params(node, id(node) in class_methods)
        if missing:
            violations.append(
                f"line {node.lineno}: def {node.name}() — parameter(s) "
                f"{', '.join(missing)} have no type hint."
            )
        if node.returns is None:
            violations.append(
                f"line {node.lineno}: def {node.name}() — no return "
                f"type hint (use `-> None` if it returns nothing)."
            )

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and not (
                target.id.startswith("__") and target.id.endswith("__")
            ):
                violations.append(
                    f"line {node.lineno}: module-level `{target.id}` has "
                    f"no type hint — write `{target.id}: <type> = ...`."
                )

    if violations:
        print("[TYPE HINT ERROR] Missing type hints:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    print("[OK] Type hint check passed")


def _find_ruff() -> str | None:
    """Prefer the ruff installed next to this interpreter (the .conda
    env), then whatever is on PATH."""
    sibling = Path(sys.executable).parent / "ruff"
    if sibling.exists():
        return str(sibling)
    return shutil.which("ruff")


def check_line_length(source: str, path: str) -> None:
    """Level 10: no line may exceed MAX_LINE_LENGTH characters — code,
    comments and docstrings alike. ruff format cannot wrap a long string
    or comment, so the length scan is the authoritative check; the
    `ruff format --check` pass additionally catches layout that would
    be reflowed at this width."""
    too_long = [
        f"line {i}: {len(line)} chars"
        for i, line in enumerate(source.splitlines(), start=1)
        if len(line) > MAX_LINE_LENGTH
    ]
    if too_long:
        print(f"[LINE LENGTH ERROR] {len(too_long)} line(s) over {MAX_LINE_LENGTH} chars:")
        for entry in too_long:
            print(f"  - {entry}")
        print(
            f"  Fix: wrap to <= {MAX_LINE_LENGTH} chars; "
            f"`ruff format --line-length {MAX_LINE_LENGTH} <file>` handles code, "
            f"comments and strings must be wrapped by hand."
        )
        sys.exit(1)

    ruff = _find_ruff()
    if ruff is None:
        print("[WARN] ruff not found — skipped `ruff format --check`.")
        print("[OK] Line length check passed (length scan only)")
        return
    proc = subprocess.run(
        [ruff, "format", "--check", "--isolated", "--line-length", str(MAX_LINE_LENGTH), path],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print("[FORMAT ERROR] ruff would reformat this file:")
        print(f"  {(proc.stdout + proc.stderr).strip()}")
        print(f"  Fix: ruff format --line-length {MAX_LINE_LENGTH} {path}")
        sys.exit(1)
    print("[OK] Line length check passed")


DESIGNATED_ACCESSOR_ROOTS = {
    "structuredData": "asset.get_data_structure(group, identifier)",
    "pageConfigurations": "asset.get_page_configuration(name, region)",
}


def check_deprecated_get(tree: ast.Module) -> None:
    """Level 11: cascade-cms-rest 3.1.6 emits a warning when
    Asset.get() is asked for structuredData / pageConfigurations, since
    those have designated accessors that return live references."""
    warnings = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            root = node.args[0].value.split(".")[0]
            if root in DESIGNATED_ACCESSOR_ROOTS:
                warnings.append(
                    f"line {node.lineno}: .get({node.args[0].value!r}) — use "
                    f"{DESIGNATED_ACCESSOR_ROOTS[root]} instead."
                )
    for w in warnings:
        print(f"[WARN] {w}")
    print("[OK] Deprecated get() check passed" + (" (with warnings)" if warnings else ""))


def main():
    if len(sys.argv) != 2:
        print("Usage: python validate_script.py path/to/generated_script.py")
        sys.exit(2)

    path = sys.argv[1]
    source = Path(path).read_text()

    print_bundle_banner()
    tree = check_syntax(source, path)
    check_type_hints(tree)
    check_line_length(source, path)
    check_wrapper_only(tree, path)
    check_imports(tree, path)
    check_operation_names(tree)
    check_asset_subscript_assignment(tree)
    check_path_identifiers(tree)
    check_chain_results_attrs(tree)
    check_result_type(tree)
    check_construction(tree, source)
    check_deprecated_get(tree)

    print("\nAll static checks passed. No network calls were made.")


if __name__ == "__main__":
    main()

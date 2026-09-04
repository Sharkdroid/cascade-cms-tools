#!/usr/bin/env python3
"""Build the cascade-cms-tools skill release bundle from tracked source.

One artifact — dist/cascade-cms-tools-skill-<version>.zip — containing the
skill (skill/cascade-script-writer/) plus the root README and LICENSE. The
MCP server (mcp/) is a separate, independently-versioned PyPI package
(cascade-cms-rest-mcp) published straight from mcp/ by
.github/workflows/release.yml's publish-pypi job — it is no longer stapled
into this zip. Neither piece requires the other to be *used*; they just
happen to share this repo and its tools-version number.

Syncs the *installed* cascade-cms-rest package into the skill bundle (this
repo holds no copy of the library's source), records a manifest, writes the
shared security gate, and validates every template against the
freshly-synced bundle before zipping — a template that fails validation
aborts the build, so a bundle can never ship having drifted from the
library it claims to validate against.

Two version numbers are in play, and they are deliberately not the same:

  tools version    cascade-cms-tools' own v0.x.x release line (this repo's
                    git tags, the bundle zip filename) - read from
                    mcp/pyproject.toml, the single source of truth.
  library version   the *installed* cascade-cms-rest version actually
                    bundled into the skill - recorded in
                    cascade_cms/_bundle_manifest.json for drift detection,
                    never used for the zip filename.

    python build_release.py                  # tools version from mcp/pyproject.toml
    python build_release.py --version 0.3.0
    python build_release.py --no-zip         # sync + validate only
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SKILL_DIR = REPO_ROOT / "skill"
SKILL_SRC = SKILL_DIR / "cascade-script-writer"
MCP_DIR = REPO_ROOT / "mcp"
MCP_PYPROJECT = MCP_DIR / "pyproject.toml"
DIST_DIR = REPO_ROOT / "dist"


def read_tools_version() -> str:
    """cascade-cms-tools' own v0.x.x version, shared by the mcp package and
    the git release tag - this is what names the bundle zip, not the
    bundled library's version."""
    text = MCP_PYPROJECT.read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        sys.exit("[BUILD ERROR] Could not find version in mcp/pyproject.toml")
    return match.group(1)


def read_library_version() -> str:
    """cascade-cms-tools has no local copy of cascade_cms's source (see
    sync_skill_snapshot below) - the installed library's own version is the
    only correct source of truth for what a freshly-built bundle actually
    bundles. Recorded in the manifest, never used for the zip filename.
    """
    try:
        return importlib.metadata.version("cascade-cms-rest")
    except importlib.metadata.PackageNotFoundError:
        sys.exit(
            "[BUILD ERROR] cascade-cms-rest is not installed in this environment - "
            "run `pip install cascade-cms-rest` (or `--upgrade` to bundle a newly-"
            "released version) before building."
        )


def sync_skill_snapshot() -> list[Path]:
    """Sync from the *installed* cascade-cms-rest package, not a local repo
    path - cascade-cms-tools is a separate repo from cascade-cms-rest, so
    there is no source tree to read here. Works whether cascade-cms-rest is
    installed normally or editable: both expose cascade_cms.__file__.
    """
    import cascade_cms

    src_pkg = Path(cascade_cms.__file__).resolve().parent
    bundle_pkg = SKILL_SRC / "cascade_cms"
    bundle_pkg.mkdir(parents=True, exist_ok=True)
    for stale in bundle_pkg.glob("*.py"):
        stale.unlink()
    copied = []
    for source in sorted(src_pkg.glob("*.py")):
        shutil.copy2(source, bundle_pkg / source.name)
        copied.append(bundle_pkg / source.name)
    print(f"[OK] Synced {len(copied)} file(s) from installed cascade_cms ({src_pkg})")
    return copied


def write_skill_manifest(library_version: str, files: list[Path]) -> None:
    manifest = SKILL_SRC / "cascade_cms" / "_bundle_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "library_version": library_version,
                "source": "src/cascade_cms",
                "files": {
                    f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files
                },
            },
            indent=2,
        )
        + "\n"
    )
    print(f"[OK] Wrote skill manifest for cascade-cms-rest {library_version}")


def write_security_gate() -> None:
    """Copy mcp/'s asset-type allowlist/blocklist into the skill bundle as a
    small data file, so validate_script.py can enforce it without the
    shipped bundle depending on the mcp package at runtime (bundle scripts
    must run with only cascade_cms + stdlib - see SKILL.md).
    mcp/src/cascade_cms_rest_mcp/security.py is the single source of truth;
    re-run this build whenever it changes."""
    sys.path.insert(0, str(MCP_DIR / "src"))
    from cascade_cms_rest_mcp import security

    out = SKILL_SRC / "references" / "blocked_asset_types.json"
    out.write_text(
        json.dumps(
            {
                "blocked": sorted(security.BLOCKED_ASSET_TYPES),
                "allowed": sorted(security.ALLOWED_ASSET_TYPES),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"[OK] Wrote security gate ({len(security.BLOCKED_ASSET_TYPES)} blocked type(s))")


def validate_templates() -> None:
    templates = sorted((SKILL_SRC / "templates").glob("*.py"))
    validator = SKILL_SRC / "scripts" / "validate_script.py"
    if not templates:
        sys.exit("[BUILD ERROR] No templates found — refusing to ship an empty bundle")

    failures = []
    for template in templates:
        proc = subprocess.run(
            [sys.executable, str(validator), str(template)],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            print(f"[OK] {template.name}")
        else:
            failures.append((template.name, proc.stdout + proc.stderr))
            print(f"[FAIL] {template.name}")

    if failures:
        print(f"\n[BUILD ABORTED] {len(failures)} template(s) failed validation:\n")
        for name, output in failures:
            print(f"--- {name} ---")
            print(output)
        sys.exit(1)
    print(f"\n[OK] All {len(templates)} templates passed validation")


def build_zip(tools_version: str) -> Path:
    DIST_DIR.mkdir(exist_ok=True)
    out = DIST_DIR / f"cascade-cms-tools-skill-{tools_version.replace('.', '')}.zip"
    root_name = "cascade-cms-tools"

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SKILL_SRC.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts or ".ruff_cache" in path.parts:
                continue
            zf.write(path, Path(root_name) / "skill" / path.relative_to(SKILL_DIR))

        for extra in ("README.md", "LICENSE"):
            zf.write(REPO_ROOT / extra, Path(root_name) / extra)

    print(f"[OK] Wrote {out.relative_to(REPO_ROOT)}")
    return out


def build(tools_version: str, zip_it: bool) -> None:
    library_version = read_library_version()
    print(f"\n=== cascade-cms-tools {tools_version} (cascade-cms-rest {library_version}) ===\n")

    files = sync_skill_snapshot()
    write_skill_manifest(library_version, files)
    write_security_gate()
    validate_templates()

    if zip_it:
        build_zip(tools_version)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="override the tools version from mcp/pyproject.toml")
    parser.add_argument("--no-zip", action="store_true", help="sync + validate only")
    args = parser.parse_args()

    tools_version = args.version or read_tools_version()
    build(tools_version, zip_it=not args.no_zip)


if __name__ == "__main__":
    main()

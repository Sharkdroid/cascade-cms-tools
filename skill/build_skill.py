#!/usr/bin/env python3
"""Build the cascade-script-writer skill package from tracked source.

One bundle from one source of truth:

  cascade-script-writer — 21 templates, full schema

Syncs the *installed* cascade-cms-rest package into the bundle (this repo
holds no copy of the library's source), records a manifest, validates every
template against the freshly-synced bundle, and only then zips. A template
that fails validation aborts the build, so a bundle can never ship having
drifted from the library it claims to validate against.

Two version numbers are in play, and they are deliberately not the same:

  tools version    cascade-cms-tools' own v0.x.x release line (this repo's
                    git tags, the .skill/mcp zip filenames) - read from
                    mcp/pyproject.toml, the single source of truth both
                    build scripts share.
  library version   the *installed* cascade-cms-rest version actually
                    bundled - recorded in cascade_cms/_bundle_manifest.json
                    for drift detection, never the tools version.

    python skill/build_skill.py                  # tools version from mcp/pyproject.toml
    python skill/build_skill.py --version 0.3.0
    python skill/build_skill.py --no-zip         # sync + validate only
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

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skill"
FULL_SRC = SKILL_DIR / "cascade-script-writer"
MCP_SRC = REPO_ROOT / "mcp" / "src"
MCP_PYPROJECT = REPO_ROOT / "mcp" / "pyproject.toml"


def read_tools_version() -> str:
    """cascade-cms-tools' own v0.x.x version, shared with the mcp package and
    the git release tag (see mcp/build_release.py's identical read_version())
    - this is what names the .skill zip, not the bundled library's version."""
    text = MCP_PYPROJECT.read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        sys.exit("[BUILD ERROR] Could not find version in mcp/pyproject.toml")
    return match.group(1)


def read_library_version() -> str:
    """cascade-cms-tools has no local copy of cascade_cms's source (see
    sync_snapshot below) - the installed library's own version is the only
    correct source of truth for what a freshly-built bundle actually bundles.
    Recorded in the manifest, never used for the zip filename.
    """
    try:
        return importlib.metadata.version("cascade-cms-rest")
    except importlib.metadata.PackageNotFoundError:
        sys.exit(
            "[BUILD ERROR] cascade-cms-rest is not installed in this environment - "
            "run `pip install cascade-cms-rest` (or `--upgrade` to bundle a newly-"
            "released version) before building."
        )


def sync_snapshot(skill_src: Path) -> list[Path]:
    """Sync from the *installed* cascade-cms-rest package, not a local repo
    path - cascade-cms-tools is a separate repo from cascade-cms-rest, so
    there is no source tree to read here. Works whether cascade-cms-rest is
    installed normally or editable: both expose cascade_cms.__file__.
    """
    import cascade_cms

    src_pkg = Path(cascade_cms.__file__).resolve().parent
    bundle_pkg = skill_src / "cascade_cms"
    bundle_pkg.mkdir(parents=True, exist_ok=True)
    for stale in bundle_pkg.glob("*.py"):
        stale.unlink()
    copied = []
    for source in sorted(src_pkg.glob("*.py")):
        shutil.copy2(source, bundle_pkg / source.name)
        copied.append(bundle_pkg / source.name)
    print(f"[OK] Synced {len(copied)} file(s) from installed cascade_cms ({src_pkg})")
    return copied


def write_manifest(skill_src: Path, library_version: str, files: list[Path]) -> None:
    manifest = skill_src / "cascade_cms" / "_bundle_manifest.json"
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
    print(f"[OK] Wrote manifest for cascade-cms-rest {library_version}")


def write_security_gate(skill_src: Path) -> None:
    """Copy mcp/'s asset-type allowlist/blocklist into the bundle as a small
    data file, so validate_script.py can enforce it without the shipped
    bundle depending on the mcp package at runtime (bundle scripts must run
    with only cascade_cms + stdlib - see SKILL.md). mcp/src/cascade_cms_rest_mcp/security.py
    is the single source of truth; re-run this build whenever it changes."""
    sys.path.insert(0, str(MCP_SRC))
    from cascade_cms_rest_mcp import security

    out = skill_src / "references" / "blocked_asset_types.json"
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


def validate_templates(skill_src: Path) -> None:
    templates = sorted((skill_src / "templates").glob("*.py"))
    validator = skill_src / "scripts" / "validate_script.py"
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


def build_zip(skill_src: Path, tools_version: str) -> Path:
    out = SKILL_DIR / f"{skill_src.name}-{tools_version.replace('.', '')}.skill"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(skill_src.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts:
                continue
            zf.write(path, path.relative_to(skill_src.parent))
    print(f"[OK] Wrote {out.relative_to(REPO_ROOT)}")
    return out


def build(tools_version: str, zip_it: bool) -> None:
    library_version = read_library_version()
    print(
        f"\n=== {FULL_SRC.name} {tools_version} "
        f"(cascade-cms-rest {library_version}) ===\n"
    )

    files = sync_snapshot(FULL_SRC)
    write_manifest(FULL_SRC, library_version, files)
    write_security_gate(FULL_SRC)
    validate_templates(FULL_SRC)

    if zip_it:
        build_zip(FULL_SRC, tools_version)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="override the tools version from mcp/pyproject.toml")
    parser.add_argument("--no-zip", action="store_true", help="sync + validate only")
    args = parser.parse_args()

    tools_version = args.version or read_tools_version()
    build(tools_version, zip_it=not args.no_zip)


if __name__ == "__main__":
    main()

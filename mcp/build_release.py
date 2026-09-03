#!/usr/bin/env python3
"""Build the cascade-cms-rest-mcp release artifact from tracked source.

Zips this directory's installable project (pyproject.toml, README.md,
src/cascade_cms_rest_mcp/) into a versioned archive under dist/, committed
into the repo the same way skill/*.skill files are - not published to PyPI,
not wired into CI. An end user downloads the zip, unpacks it, and points
`uvx --from <unpacked-dir> cascade-cms-rest-mcp` at it (see README.md).

    python mcp/build_release.py                  # version from pyproject.toml
    python mcp/build_release.py --version 0.2.0
    python mcp/build_release.py --no-zip          # validate only, skip the zip
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parent
DIST_DIR = MCP_DIR / "dist"

# Everything a downstream `uvx --from <unpacked-dir> cascade-cms-rest-mcp`
# needs to resolve dependencies and find the console-script entry point.
INCLUDE = ("pyproject.toml", "README.md", "src")


def read_version() -> str:
    text = (MCP_DIR / "pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        sys.exit("[BUILD ERROR] Could not find version in mcp/pyproject.toml")
    return match.group(1)


def collect_files() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE:
        source = MCP_DIR / name
        if source.is_file():
            files.append(source)
        elif source.is_dir():
            for path in sorted(source.rglob("*")):
                if path.is_dir() or "__pycache__" in path.parts:
                    continue
                files.append(path)
        else:
            sys.exit(f"[BUILD ERROR] Expected {name} in {MCP_DIR}, not found")
    return files


def build_zip(version: str) -> Path:
    DIST_DIR.mkdir(exist_ok=True)
    out = DIST_DIR / f"cascade-cms-rest-mcp-{version.replace('.', '')}.zip"
    files = collect_files()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, Path("cascade-cms-rest-mcp") / path.relative_to(MCP_DIR))
    print(f"[OK] Wrote {out.relative_to(MCP_DIR.parent)} ({len(files)} file(s))")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="override version from pyproject.toml")
    parser.add_argument(
        "--no-zip", action="store_true", help="validate only, skip the zip"
    )
    args = parser.parse_args()

    version = args.version or read_version()
    print(f"=== cascade-cms-rest-mcp {version} ===")

    files = collect_files()
    print(f"[OK] {len(files)} file(s) staged for release")

    if not args.no_zip:
        build_zip(version)


if __name__ == "__main__":
    main()

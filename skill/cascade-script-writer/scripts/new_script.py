#!/usr/bin/env python3
"""Scaffold a new script from a validated template.

Copying a known-good template beats writing structure from memory: the result
already passes the validator, so only the task-specific edits can break it.

    python scripts/new_script.py --list
    python scripts/new_script.py --template create-bulk --out my_script.py
    python scripts/new_script.py --template read-identifiers --out r.py --site www
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL_ROOT / "templates"


def available() -> list[str]:
    return sorted(p.stem for p in TEMPLATES.glob("*.py"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", help="template name (without .py)")
    parser.add_argument("--out", help="destination path for the new script")
    parser.add_argument("--site", help="replace the SITE_NAME placeholder")
    parser.add_argument("--list", action="store_true", help="list templates and exit")
    args = parser.parse_args()

    if args.list or not args.template:
        print("Available templates:\n")
        for name in available():
            print(f"  {name}")
        print(f"\nSee {TEMPLATES.relative_to(SKILL_ROOT)}/INDEX.md to pick by task shape.")
        sys.exit(0 if args.list else 2)

    source = TEMPLATES / f"{args.template}.py"
    if not source.exists():
        import difflib

        close = difflib.get_close_matches(args.template, available(), n=3)
        print(f"[ERROR] No template named '{args.template}'.")
        if close:
            print(f"        Did you mean: {', '.join(close)}?")
        print("        Run with --list to see all templates.")
        sys.exit(1)

    if not args.out:
        print("[ERROR] --out is required when --template is given.")
        sys.exit(2)

    destination = Path(args.out)
    if destination.exists():
        print(f"[ERROR] {destination} already exists — refusing to overwrite.")
        sys.exit(1)

    text = source.read_text()
    if args.site:
        text = text.replace('SITE_NAME = "www"', f'SITE_NAME = "{args.site}"')
        text = text.replace('"siteName": "www"', f'"siteName": "{args.site}"')

    destination.write_text(text)
    print(f"[OK] Wrote {destination} from template '{args.template}'")
    print("\nNext:")
    print(f"  1. Edit the Configuration block and the task-specific values in {destination}")
    print(f"  2. python {Path(__file__).parent / 'validate_script.py'} {destination}")
    print("  3. Fix anything it reports, then re-run until it exits 0")


if __name__ == "__main__":
    main()

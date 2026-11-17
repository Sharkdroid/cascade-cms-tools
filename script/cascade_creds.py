#!/usr/bin/env python3
"""Rotate Cascade CMS credentials for a Claude Code MCP entry.

Usage (run from the folder you use with Claude Code):
    python scripts/cascade_creds.py                       # user scope, cascade-cms
    python scripts/cascade_creds.py --name cascade-cms-prod
    python scripts/cascade_creds.py --scope local         # this project only
    python scripts/cascade_creds.py --claude-settings-path ~/alt/.claude.json

Stdlib only. Requires the `claude` CLI on PATH.
"""

import argparse
import getpass
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_NAME = "cascade-cms"
KEY_VAR = "CASCADE_API_KEY"
URL_VAR = "CASCADE_URL"
DEFAULT_COMMAND = "uvx"
DEFAULT_ARGS = ["--no-cache", "cascade-cms-rest-mcp"]
MANUAL_HINT = "Manual steps: see 'Credentials' in README.md."
DEFAULT_CONFIG = Path.home() / ".claude.json"
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def server_name(value):
    """argparse type: accept only names the claude CLI can store."""
    if not NAME_PATTERN.match(value):
        raise argparse.ArgumentTypeError("use only letters, digits, '-' and '_'")
    return value


def load_config(config):
    """Return the parsed config, or None if the file does not exist."""
    if not config.exists():
        return None
    try:
        return json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"error: could not read {config}: {exc}\n{MANUAL_HINT}")


def servers_for(data, scope):
    """Return the cascade MCP entries visible in this scope.

    user  -> top-level mcpServers
    local -> projects.<current folder>.mcpServers
    """
    if not data:
        return {}
    if scope == "user":
        return data.get("mcpServers", {})
    project = data.get("projects", {}).get(str(Path.cwd()), {})
    return project.get("mcpServers", {})


def normalize_url(url):
    return (url or "").strip().lower().rstrip("/")


def find_duplicates(servers, name, url):
    """Return other entry names in this scope that use the same URL."""
    wanted = normalize_url(url)
    if not wanted:
        return []
    return sorted(other for other, entry in servers.items() if other != name and normalize_url(entry.get("env", {}).get(URL_VAR)) == wanted)


def run_claude(claude, args):
    return subprocess.run([claude, *args], capture_output=True, text=True, check=False)


def echo_failure(result):
    """Print the CLI's own error output so the user can fix it."""
    for stream in (result.stderr, result.stdout):
        if stream and stream.strip():
            print(stream.rstrip(), file=sys.stderr)


def add_args(name, scope, env, command, cmd_args):
    args = ["mcp", "add", name, "-s", scope]
    for key, value in env.items():
        args += ["-e", f"{key}={value}"]
    args += ["--", command, *cmd_args]
    return args


def prompt_url(current):
    prompt = f"Cascade URL [{current}]: " if current else "Cascade URL: "
    value = input(prompt).strip() or current
    if not value:
        sys.exit("error: a Cascade URL is required.")
    return value


def confirm_duplicates(name, dups):
    print(
        f"warning: '{name}' and {', '.join(dups)} use the same Cascade URL.",
        file=sys.stderr,
    )
    answer = input("Continue anyway? [y/N]: ").strip().lower()
    return answer == "y"


def main():
    parser = argparse.ArgumentParser(description="Rotate Cascade CMS credentials.")
    parser.add_argument(
        "--name",
        type=server_name,
        default=DEFAULT_NAME,
        help=f"MCP entry to update (default: {DEFAULT_NAME})",
    )
    parser.add_argument(
        "--scope",
        choices=["user", "local"],
        default="user",
        help="user (default, all projects) or local (this project only)",
    )
    parser.add_argument(
        "--claude-settings-path",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Claude config file to read (default: {DEFAULT_CONFIG})",
    )
    args = parser.parse_args()
    config = args.claude_settings_path.expanduser()

    claude = shutil.which("claude")
    if not claude:
        print("error: 'claude' CLI not found on PATH.", file=sys.stderr)
        print(MANUAL_HINT, file=sys.stderr)
        return 1

    servers = servers_for(load_config(config), args.scope)
    existing = servers.get(args.name)
    current_url = (existing or {}).get("env", {}).get(URL_VAR, "")

    url = prompt_url(current_url)

    dups = find_duplicates(servers, args.name, url)
    if dups and not confirm_duplicates(args.name, dups):
        print("Nothing changed.", file=sys.stderr)
        return 1

    key = getpass.getpass("Cascade API key (hidden): ").strip()
    if not key:
        print("error: an API key is required. Nothing changed.", file=sys.stderr)
        return 1

    if existing is not None:
        removed = run_claude(claude, ["mcp", "remove", args.name, "-s", args.scope])
        if removed.returncode != 0:
            print(
                "error: could not remove the existing entry. Nothing changed.",
                file=sys.stderr,
            )
            echo_failure(removed)
            return 1

    new_env = {KEY_VAR: key, URL_VAR: url}
    added = run_claude(
        claude,
        add_args(args.name, args.scope, new_env, DEFAULT_COMMAND, DEFAULT_ARGS),
    )
    if added.returncode == 0:
        print(f"Credentials updated: '{args.name}' ({args.scope} scope).")
        return 0

    print("error: 'claude mcp add' failed:", file=sys.stderr)
    echo_failure(added)

    if existing is None:
        print("No previous entry existed, so nothing to restore.", file=sys.stderr)
        return 1

    # Restore the previous entry from values already read into memory.
    restored = run_claude(
        claude,
        add_args(
            args.name,
            args.scope,
            existing.get("env", {}),
            existing.get("command", DEFAULT_COMMAND),
            existing.get("args", DEFAULT_ARGS),
        ),
    )
    if restored.returncode == 0:
        print(
            "The previous entry was restored. Fix the error above and run again.",
            file=sys.stderr,
        )
    else:
        print("error: restoring the previous entry also failed.", file=sys.stderr)
        echo_failure(restored)
        print(MANUAL_HINT, file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled. Nothing changed.", file=sys.stderr)
        sys.exit(1)

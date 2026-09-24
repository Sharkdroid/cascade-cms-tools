"""M1: stdout carries only JSON-RPC; library status lines go to stderr."""

import json
import os
import subprocess
import sys


def _msg(id_, method, params=None):
    body = {"jsonrpc": "2.0", "method": method}
    if id_ is not None:
        body["id"] = id_
    if params is not None:
        body["params"] = params
    return json.dumps(body) + "\n"


def test_stdout_is_protocol_clean(tmp_path):
    env = {
        **os.environ,
        "CASCADE_API_KEY": "dummy-key-1234",
        "CASCADE_URL": "https://invalid.example",
        "CASCADE_MCP_LOG_DIR": str(tmp_path / "logs"),
    }
    stdin = (
        _msg(
            1,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"},
            },
        )
        + _msg(None, "notifications/initialized")
        + _msg(
            2,
            "tools/call",
            {"name": "cascade_list_sites", "arguments": {}},
        )
    )
    proc = subprocess.run(
        [sys.executable, "-m", "cascade_cms_rest_mcp.server"],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines
    for line in lines:
        assert json.loads(line)["jsonrpc"] == "2.0"
    # The tool call reaches the library (and fails on the unreachable
    # host), so its status lines must be on stderr, never stdout.
    assert "[INIT]" in proc.stderr
    assert "[INIT]" not in proc.stdout

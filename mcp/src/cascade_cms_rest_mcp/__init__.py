"""cascade-cms-rest-mcp - a local, read-only MCP server wrapping cascade_cms.

Lives in its own repo/project (cascade-cms-tools/mcp/), not inside
cascade-cms-rest itself: the `mcp` SDK dependency, and this package's own
release cadence, are both independent of the library it wraps. A normal
`pip install cascade-cms-rest` is completely unaffected by this package's
existence.
"""

from http.cookies import Morsel

# CPython < 3.14 doesn't recognize the "partitioned" Set-Cookie attribute
# (added in gh-112713 / bpo-112713, landed in 3.14). aiohttp >= 3.10 emits
# it whenever a server's Set-Cookie header carries "Partitioned", and
# aiohttp-client-cache (a cascade_cms dependency) parses every cached
# response's cookies via http.cookies.SimpleCookie.load(), which raises
# CookieError("Invalid attribute 'partitioned'") on such a header under
# 3.12/3.13. Cascade CMS sends Partitioned on its session cookie, so every
# call fails. Registering the attribute here (before any cookie parsing
# happens) makes Morsel accept it on all supported Python versions;
# harmless no-op once running under 3.14+, which already knows it.
if "partitioned" not in Morsel._reserved:  # type: ignore[attr-defined]
    Morsel._reserved["partitioned"] = "Partitioned"  # type: ignore[attr-defined]
    Morsel._flags.add("partitioned")  # type: ignore[attr-defined]

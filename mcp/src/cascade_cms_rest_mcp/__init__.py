"""cascade-cms-rest-mcp - a local, read-only MCP server wrapping cascade_cms.

Lives in its own repo/project (cascade-cms-tools/mcp/), not inside
cascade-cms-rest itself: the `mcp` SDK dependency, and this package's own
release cadence, are both independent of the library it wraps. A normal
`pip install cascade-cms-rest` is completely unaffected by this package's
existence.
"""

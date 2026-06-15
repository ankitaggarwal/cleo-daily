"""cleo-mcp-x — SCAFFOLD. A curated X/Twitter list, as a source.

Template for the "MCP source" extension point. Wire the body to the X API (use
X_BEARER_TOKEN), map each post into the Item shape, return {"items": [...]}.
Until then it returns nothing, so enabling `signals` degrades to empty.

Run standalone:   python -m servers.x.server
"""

from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cleo-x")


@mcp.tool()
def home_timeline(lists: list[str] | None = None, limit: int = 40) -> str:
    """Return Item-shaped rows for posts from `lists`. TODO: implement.

    Map each post → {id, beat:"signals", source:<@handle>, title:<text>,
    url:<status url>, published:<date>, text:<text>, metrics:{likes,reposts}}.
    """
    token = os.environ.get("X_BEARER_TOKEN")  # noqa: F841 — wire me up
    items: list[dict] = []
    return json.dumps({"items": items}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()

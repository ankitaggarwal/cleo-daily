"""cleo-mcp-gmail — SCAFFOLD. The reader's newsletters, as a source.

A working template for the "MCP source" extension point. Wire the body to the
Gmail API (use GMAIL_OAUTH_TOKEN), map each message into the Item shape, and
return {"items": [...]}. Until then it returns nothing, so enabling `inbox`
degrades to empty rather than breaking a run.

Run standalone:   python -m servers.gmail.server
"""

from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cleo-gmail")


@mcp.tool()
def search(query: str = "label:newsletters newer_than:2d", limit: int = 40) -> str:
    """Return Item-shaped rows for matching messages. TODO: implement.

    Map each message → {id, beat:"inbox", source:<sender>, title:<subject>,
    url:<permalink>, published:<date>, text:<plain body>}.
    """
    token = os.environ.get("GMAIL_OAUTH_TOKEN")  # noqa: F841 — wire me up
    items: list[dict] = []
    return json.dumps({"items": items}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()

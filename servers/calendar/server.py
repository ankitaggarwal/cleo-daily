"""cleo-mcp-calendar — SCAFFOLD. Your week ahead, for the Desk.

Template for the "MCP source" extension point. Wire the body to your calendar
(use GOOGLE_CALENDAR_TOKEN), map each event into the Item shape, return
{"items": [...]}. Until then it returns nothing, so enabling `calendar`
degrades to empty.

Run standalone:   python -m servers.calendar.server
"""

from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cleo-calendar")


@mcp.tool()
def upcoming(days: int = 3) -> str:
    """Return Item-shaped rows for the next `days` of events. TODO: implement.

    Map each event → {id, beat:"personal", source:"Calendar", title:<summary>,
    published:<start>, text:<when + where>}.
    """
    token = os.environ.get("GOOGLE_CALENDAR_TOKEN")  # noqa: F841 — wire me up
    items: list[dict] = []
    return json.dumps({"items": items}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()

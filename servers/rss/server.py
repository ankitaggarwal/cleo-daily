"""cleo-mcp-rss — the RSS/Atom source, exposed over MCP for a Claude routine.

This is the keystone source: the whole default roster is feeds, and it needs no
keys. The fetch logic is `cleo.sources.rss` — the *same* code the `cleo` CLI
uses directly — so there is one implementation, wrapped here for the routine.

Run standalone:   python -m servers.rss.server
In .mcp.json:     { "command": "python", "args": ["-m", "servers.rss.server"] }
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from cleo.sources.rss import fetch_feeds as _fetch

mcp = FastMCP("cleo-rss")


@mcp.tool()
def fetch_feeds(feeds: list[str], since: str = "2d", beat: str = "wire", per_feed: int = 25) -> str:
    """Fetch RSS/Atom feeds and return Item-shaped rows as JSON.

    Args:
        feeds:    feed URLs to pull.
        since:    recency window, e.g. "2d", "36h", "90m".
        beat:     the lens to stamp on every item (strategy, product, wire, …).
        per_feed: cap on entries kept per feed.
    """
    items = _fetch(feeds, since=since, beat=beat, per_feed=per_feed)
    return json.dumps({"items": items}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()

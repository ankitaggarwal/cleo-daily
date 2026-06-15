"""Step 1 of the loop: pull every active source, normalize, dedupe, window.

For `server = "rss"` we call the built-in adapter directly (no process to
spawn). For any other server we connect to it over MCP using the launch config
in `.mcp.json` — that's how the reader's own lenses (gmail, x, calendar, …)
arrive. The Item schema is the only thing downstream ever sees.

Output: `runs/<date>/items.jsonl`. A dead source is logged and skipped; it
never blocks an issue.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .config import Config
from .schema import Item
from .sources import rss

log = logging.getLogger("cleo.ingest")


def _dedupe(items: list[Item]) -> list[Item]:
    seen: set[str] = set()
    out: list[Item] = []
    for it in items:
        key = it.id or (it.url or it.title)
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _from_rss(src) -> list[dict[str, Any]]:
    feeds = src.args.get("feeds", [])
    since = src.args.get("since", "2d")
    if not feeds:
        log.warning("rss source on beat %r has no feeds", src.beat)
        return []
    return rss.fetch_feeds(feeds, since=since, beat=src.beat)


def _from_mcp(cfg: Config, src) -> list[dict[str, Any]]:
    """Connect to an MCP server declared in .mcp.json and call its tool.

    Lazy-imported so users on the default RSS roster never need the MCP SDK.
    """
    try:
        from .mcpclient import call_tool  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        log.warning("mcp source %r skipped — MCP client unavailable (%s)", src.beat, exc)
        return []
    try:
        return call_tool(cfg.root, src.server, src.tool, src.args, beat=src.beat)
    except Exception as exc:  # noqa: BLE001
        log.warning("mcp source %r (%s/%s) failed: %s", src.beat, src.server, src.tool, exc)
        return []


def ingest(cfg: Config, run_dir: Path) -> list[Item]:
    raw: list[dict[str, Any]] = []
    for src in cfg.sources(active_only=True):
        rows = _from_rss(src) if src.server == "rss" else _from_mcp(cfg, src)
        log.info("source %-10s %-8s → %d", src.beat, src.server, len(rows))
        raw.extend(rows)

    items: list[Item] = []
    for row in raw:
        try:
            items.append(Item.model_validate(row))
        except Exception as exc:  # noqa: BLE001
            log.debug("dropping malformed item: %s", exc)
    items = _dedupe(items)

    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "items.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for it in items:
            fh.write(it.model_dump_json(exclude_none=False) + "\n")
    log.info("ingested %d items → %s", len(items), out)
    return items

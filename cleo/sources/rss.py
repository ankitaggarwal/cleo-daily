"""The built-in RSS/Atom adapter.

Fetches a list of feeds, windows them by recency, and maps each entry into the
Item schema. Deliberately self-contained: this is both the engine's default
source *and* the body of the shipped `rss` MCP server, so there is one
implementation, not two.

Two small robustnesses learned the hard way:
  * a browser-grade User-Agent — several publishers (The Verge, Ars, SVPG)
    return 403 to the default feedparser UA;
  * one dead feed never blocks an issue — failures are logged and skipped.
"""

from __future__ import annotations

import calendar
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

log = logging.getLogger("cleo.rss")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 CleoDaily/0.2 (+https://github.com/ankitaggarwal/cleo-daily)"
)

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _since_cutoff(since: str) -> Optional[datetime]:
    """Parse a window like '2d', '36h', '90m' into a UTC cutoff datetime."""
    if not since:
        return None
    m = re.fullmatch(r"(\d+)\s*([dhm])", since.strip().lower())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    delta = {"d": timedelta(days=n), "h": timedelta(hours=n), "m": timedelta(minutes=n)}[unit]
    return datetime.now(timezone.utc) - delta


def _clean(html: str, limit: int = 6000) -> str:
    text = _WS.sub(" ", _TAG.sub(" ", html or "")).strip()
    return text[:limit]


def _entry_dt(entry: Any) -> Optional[datetime]:
    # feedparser normalizes RSS *and* Atom dates into a UTC struct_time.
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)
    return None


def _stable_id(url: str, title: str, source: str) -> str:
    return hashlib.sha1(f"{url}|{title}|{source}".encode("utf-8")).hexdigest()[:16]


def fetch_feeds(
    feeds: list[str],
    since: str = "2d",
    beat: str = "wire",
    per_feed: int = 25,
) -> list[dict[str, Any]]:
    """Pull `feeds`, keep entries newer than `since`, return Item-shaped dicts.

    Returns plain dicts (not pydantic models) so this is trivially JSON-able
    over MCP. The ingest layer validates them into `Item`.
    """
    import feedparser  # local import: keeps the dep optional for non-RSS users
    import httpx

    cutoff = _since_cutoff(since)
    items: list[dict[str, Any]] = []

    with httpx.Client(
        headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"},
        follow_redirects=True,
        timeout=20.0,
    ) as client:
        for feed_url in feeds:
            try:
                resp = client.get(feed_url)
                resp.raise_for_status()
                parsed = feedparser.parse(resp.content)
            except Exception as exc:  # noqa: BLE001 — a dead feed must never block an issue
                log.warning("rss: skipping %s (%s)", feed_url, exc)
                continue

            source = (parsed.feed.get("title") or feed_url).strip()
            kept = 0
            for entry in parsed.entries:
                if kept >= per_feed:
                    break
                published = _entry_dt(entry)
                if cutoff and published and published < cutoff:
                    continue
                title = (entry.get("title") or "").strip()
                url = (entry.get("link") or "").strip()
                if not title:
                    continue
                body = ""
                if entry.get("content"):
                    body = entry["content"][0].get("value", "")
                body = body or entry.get("summary", "") or entry.get("description", "")
                items.append(
                    {
                        "id": _stable_id(url, title, source),
                        "beat": beat,
                        "source": source,
                        "title": title,
                        "url": url or None,
                        "author": (entry.get("author") or None),
                        "published": published.isoformat() if published else None,
                        "text": _clean(body),
                        "media": [],
                        "metrics": {},
                        "raw": {"feed": feed_url},
                    }
                )
                kept += 1
            log.info("rss: %s → %d items", source, kept)
    return items

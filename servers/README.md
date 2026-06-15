# Supporting MCP servers

Every source is an MCP server. These are the ones a Cleo routine connects to, declared in
`.mcp.json` (copy from [`.mcp.json.example`](../.mcp.json.example)).

| Server | Status | Key | Tool | Feeds |
|---|---|---|---|---|
| [`rss`](rss/) | **working** | none | `fetch_feeds(feeds, since, beat, per_feed)` | the whole default roster |
| [`weather`](weather/) | **working** | none | `today(lat, lon, place)` | the cover weather line |
| [`gmail`](gmail/) | scaffold | `GMAIL_OAUTH_TOKEN` | `search(query, limit)` | `inbox` |
| [`x`](x/) | scaffold | `X_BEARER_TOKEN` | `home_timeline(lists, limit)` | `signals` |
| [`calendar`](calendar/) | scaffold | `GOOGLE_CALENDAR_TOKEN` | `upcoming(days)` | `calendar` |

`rss` is the keystone: the same `cleo.sources.rss.fetch_feeds` the CLI uses directly, wrapped for
the routine — one implementation, not two.

## The contract

A tool returns a JSON string `{"items": [ <Item>, ... ]}`. The [Item schema](../cleo/schema.py):

```jsonc
{ "id": "...", "beat": "...", "source": "...", "title": "...",
  "url": "...", "published": "ISO-8601", "text": "...", "metrics": {} }
```

`id` is a stable dedupe key; `beat` is stamped by the ingest layer if you omit it. Anything you
can read becomes a source by writing (or installing) a server that speaks this contract.

## Write one

Copy a scaffold (`gmail/server.py` is the smallest), point it at your API, map each record into
the Item shape, and add it to `.mcp.json` + a `[[sources]]` block. Run it standalone to test:

```bash
python -m servers.rss.server      # then drive it with an MCP client
```

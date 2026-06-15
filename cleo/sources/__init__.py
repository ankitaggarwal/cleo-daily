"""Source adapters — they all map raw content *into* the Item schema.

`rss` is built in (no key, no external process) and is also what the shipped
`rss` MCP server wraps, so the fetch logic lives in exactly one place. Personal
sources (gmail, x, calendar, …) are reached over MCP at ingest time.
"""

"""A thin synchronous MCP client for ingest.

Reads `.mcp.json` (the standard Claude Code MCP config), launches the named
server over stdio, calls one tool, and returns whatever JSON it produced as a
list of Item-shaped dicts. Used only for non-RSS sources, so the `mcp` SDK is
an optional dependency (`pip install 'cleo-daily[mcp]'`).

Server env values support `${VAR}` interpolation from the process environment
(which `cleo` has already populated from `.env`).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

_VAR = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return _VAR.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, list):
        return [_expand(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    return value


def _server_config(root: Path, server: str) -> dict[str, Any]:
    path = root / ".mcp.json"
    if not path.exists():
        raise FileNotFoundError(f"no .mcp.json at {path} (copy .mcp.json.example)")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    servers = cfg.get("mcpServers", {})
    if server not in servers:
        raise KeyError(f"server {server!r} not found in .mcp.json")
    return _expand(servers[server])


def _coerce_items(payload: Any, beat: str) -> list[dict[str, Any]]:
    """Accept either a list of items or {'items': [...]}; stamp the beat."""
    rows = payload.get("items", []) if isinstance(payload, dict) else payload
    out: list[dict[str, Any]] = []
    for row in rows or []:
        if isinstance(row, dict):
            row.setdefault("beat", beat)
            out.append(row)
    return out


async def _call(root: Path, server: str, tool: str, args: dict[str, Any], beat: str) -> list[dict[str, Any]]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    sc = _server_config(root, server)
    params = StdioServerParameters(
        command=sc["command"],
        args=sc.get("args", []),
        env={**os.environ, **sc.get("env", {})},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            rows: list[dict[str, Any]] = []
            for block in result.content:
                text = getattr(block, "text", None)
                if not text:
                    continue
                try:
                    rows.extend(_coerce_items(json.loads(text), beat))
                except json.JSONDecodeError:
                    continue
            return rows


def call_tool(root: Path, server: str, tool: str, args: dict[str, Any], beat: str) -> list[dict[str, Any]]:
    return asyncio.run(_call(root, server, tool, args, beat))

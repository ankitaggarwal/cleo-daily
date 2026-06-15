"""The Editor — optional local runner.

In production the *routine* is the Editor: a scheduled Claude Code agent reads
`cleo/skill/cleo-editor.md`, the items, and the recent issues, and writes
`issue.json` itself. This module lets you run that same step locally, without a
routine, by calling the Anthropic API with the very same skill as the system
prompt. Needs `pip install 'cleo-daily[edit]'` and ANTHROPIC_API_KEY.

It is deliberately a thin bridge — all the taste lives in the skill, not here.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from .config import Config
from .schema import Issue, Item

log = logging.getLogger("cleo.edit")

DEFAULT_MODEL = os.environ.get("CLEO_EDITOR_MODEL", "claude-opus-4-8")
SKILL = Path("cleo/skill/cleo-editor.md")


def _skill_text(root: Path) -> str:
    p = root / SKILL
    if not p.exists():
        raise FileNotFoundError(f"editor skill not found at {p}")
    return p.read_text(encoding="utf-8")


def _compact(items: list[Item], max_items: int, snippet: int) -> list[dict[str, Any]]:
    rows = []
    for it in items[:max_items]:
        rows.append({
            "beat": it.beat,
            "source": it.source,
            "title": it.title,
            "url": it.url,
            "published": it.published.isoformat() if it.published else None,
            "text": (it.text or "")[:snippet],
        })
    return rows


def _recent_issues(root: Path, n: int) -> list[str]:
    runs = sorted((root / "runs").glob("*/issue.json")) if (root / "runs").exists() else []
    return [p.read_text(encoding="utf-8")[:4000] for p in runs[-n:]]


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        text = text[4:] if text.startswith("json") else text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in the Editor's reply")
    return json.loads(text[start : end + 1])


def edit(
    cfg: Config,
    items: list[Item],
    *,
    model: str = DEFAULT_MODEL,
    max_items: int = 220,
    snippet: int = 600,
) -> Issue:
    try:
        import anthropic
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError("install the editor extra: pip install 'cleo-daily[edit]'") from exc

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    persona = cfg.persona
    recent = _recent_issues(cfg.root, 5) if cfg.on("dedupe") else []

    user = (
        f"PERSONA / BRIEF:\n{json.dumps(persona, indent=2)}\n\n"
        f"PUBLICATION: {json.dumps(cfg.publication)}\n\n"
        f"TODAY'S CANDIDATE ITEMS ({len(items)} scanned), as JSON:\n"
        f"{json.dumps(_compact(items, max_items, snippet), ensure_ascii=False)}\n\n"
        + (f"RECENT ISSUES (dedupe against these):\n{json.dumps(recent)[:8000]}\n\n" if recent else "")
        + "Apply the Doctrine. Emit ONLY the issue.json object (the Output contract). "
        "Set counts honestly. No prose outside the JSON."
    )

    log.info("editor: calling %s over %d items", model, len(items))
    resp = client.messages.create(
        model=model,
        max_tokens=16000,
        system=_skill_text(cfg.root),
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    issue = Issue.model_validate(_extract_json(text))
    # ground the scanned count if the model under-reports
    issue.counts.scanned = max(issue.counts.scanned, len(items))
    return issue

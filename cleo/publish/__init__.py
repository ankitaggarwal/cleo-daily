"""Step 6: ship the finished artifact. Zero or more targets, run in order.

Each target is a tiny function ``(artifact, options, cfg) -> str`` registered
below. Adding a publisher = one function + a ``[[publish]]`` block in cleo.toml.
Publishing only ever moves an already-built artifact; it never touches content.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from ..config import Config

log = logging.getLogger("cleo.publish")

Artifact = dict[str, Path]  # {"pdf": ..., "html": ...}
Publisher = Callable[[Artifact, dict[str, Any], Config], str]

_REGISTRY: dict[str, Publisher] = {}


def register(name: str) -> Callable[[Publisher], Publisher]:
    def deco(fn: Publisher) -> Publisher:
        _REGISTRY[name] = fn
        return fn
    return deco


def publish(cfg: Config, artifact: Artifact) -> list[str]:
    from . import file, git, email, web  # noqa: F401 — populate the registry

    results: list[str] = []
    for tgt in cfg.publish_targets(active_only=True):
        fn = _REGISTRY.get(tgt.type)
        if not fn:
            log.warning("no publisher for type %r — skipping", tgt.type)
            continue
        try:
            results.append(fn(artifact, tgt.options, cfg))
        except Exception as exc:  # noqa: BLE001 — one bad target never blocks the rest
            log.error("publish %s failed: %s", tgt.type, exc)
    return results

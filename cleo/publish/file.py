"""file — write the PDF (+ HTML source) into a dated folder."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from ..config import Config
from . import Artifact, register

log = logging.getLogger("cleo.publish.file")


@register("file")
def to_file(artifact: Artifact, options: dict[str, Any], cfg: Config) -> str:
    dest = (cfg.root / options.get("path", "editions/")).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    stamp = options.get("name") or _slug(cfg)
    written = []
    for kind in ("pdf", "html"):
        src = artifact.get(kind)
        if src and src.exists():
            target = dest / f"{stamp}.{kind}"
            shutil.copy2(src, target)
            written.append(target.name)
    log.info("wrote %s → %s", ", ".join(written), dest)
    return f"file: {dest}/{stamp}.*"


def _slug(cfg: Config) -> str:
    name = cfg.publication.get("name", "edition").lower().replace(" ", "-")
    return name

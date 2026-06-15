"""web — push the published edition to a web target (a deploy hook).

The simplest useful contract: POST the PDF to a URL (a Cloudflare/Netlify build
hook, a bucket signer, your own endpoint). Set CLEO_WEB_TARGET in .env.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from ..config import Config
from . import Artifact, register

log = logging.getLogger("cleo.publish.web")


@register("web")
def to_web(artifact: Artifact, options: dict[str, Any], cfg: Config) -> str:
    import httpx

    target = options.get("target") or os.environ.get("CLEO_WEB_TARGET", "")
    if not target:
        return "web: no target"
    pdf = artifact.get("pdf")
    files = {"file": (pdf.name, pdf.read_bytes(), "application/pdf")} if pdf and pdf.exists() else None
    r = httpx.post(target, files=files, timeout=60.0)
    r.raise_for_status()
    log.info("web: pushed to %s (%s)", target, r.status_code)
    return f"web: pushed ({r.status_code})"

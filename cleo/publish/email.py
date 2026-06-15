"""email — send the finished PDF to a list via Resend.

Gated by [features] email (needs RESEND_API_KEY + CLEO_SUBSCRIBERS). If the
key is absent the feature is already off upstream, so this only runs when live.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

from ..config import Config
from . import Artifact, register

log = logging.getLogger("cleo.publish.email")


@register("email")
def to_email(artifact: Artifact, options: dict[str, Any], cfg: Config) -> str:
    import httpx

    key = os.environ["RESEND_API_KEY"]
    to = options.get("to") or os.environ.get("CLEO_SUBSCRIBERS", "")
    recipients = [a.strip() for a in (to if isinstance(to, list) else to.split(",")) if a.strip()]
    if not recipients:
        return "email: no subscribers"

    pdf = artifact.get("pdf")
    name = cfg.publication.get("name", "Cleo Daily")
    payload: dict[str, Any] = {
        "from": options.get("from", f"{name} <onboarding@resend.dev>"),
        "to": recipients,
        "subject": options.get("subject", f"{name} — today's edition"),
        "text": "Today's edition is attached. Read hundreds, keep a tenth, print on paper.",
    }
    if pdf and pdf.exists():
        payload["attachments"] = [{
            "filename": pdf.name,
            "content": base64.b64encode(pdf.read_bytes()).decode("ascii"),
        }]
    r = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {key}"},
        json=payload, timeout=30.0,
    )
    r.raise_for_status()
    log.info("email: sent to %d recipient(s)", len(recipients))
    return f"email: sent to {len(recipients)}"

"""git — commit the freshly published edition to the repo (archive site)."""

from __future__ import annotations

import logging
import subprocess
from typing import Any

from ..config import Config
from . import Artifact, register

log = logging.getLogger("cleo.publish.git")


@register("git")
def to_git(artifact: Artifact, options: dict[str, Any], cfg: Config) -> str:
    msg = options.get("message", "New edition")
    path = options.get("path", "editions/")
    subprocess.run(["git", "-C", str(cfg.root), "add", path], check=True)
    proc = subprocess.run(
        ["git", "-C", str(cfg.root), "commit", "-m", msg],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 and "nothing to commit" in (proc.stdout + proc.stderr):
        log.info("git: nothing to commit")
        return "git: nothing to commit"
    proc.check_returncode()
    log.info("git: committed %r", msg)
    return f"git: committed {msg!r}"

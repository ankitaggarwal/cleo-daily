"""Step 5: issue.json + theme → self-contained HTML → headless Chrome → PDF.

Deterministic and theme-driven. The Editor decides what each section *says*;
the theme decides how it *looks*. Unknown section types degrade to a generic
block and are logged, never dropped.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .schema import Issue

log = logging.getLogger("cleo.render")

try:  # 3.11+
    import tomllib
except ModuleNotFoundError:  # 3.10
    import tomli as tomllib  # type: ignore

# Where the headless browser lives. Override with CLEO_CHROME.
_CHROME_CANDIDATES = [
    os.environ.get("CLEO_CHROME", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
]


def _find_chrome() -> Optional[str]:
    for c in _CHROME_CANDIDATES:
        if c and Path(c).exists():
            return c
    return None


def _theme_dir(root: Path, name: str) -> Path:
    d = root / "themes" / name
    if not d.exists():
        raise FileNotFoundError(f"theme {name!r} not found at {d}")
    return d


def _contents(sections: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    """A cover teaser: the headlined features, in order."""
    out = []
    for s in sections:
        if s.get("headline"):
            out.append({"headline": s["headline"], "kicker": s.get("kicker", ""), "type": s["type"]})
        if len(out) >= limit:
            break
    return out


def render(
    issue_path: Path,
    root: Path,
    theme: str = "broadsheet-mono",
    out_dir: Optional[Path] = None,
    pdf: bool = True,
) -> dict[str, Path]:
    issue = Issue.from_json(issue_path.read_text(encoding="utf-8"))
    data = issue.model_dump()
    masthead, counts = data["masthead"], data["counts"]
    sections = data["sections"]

    tdir = _theme_dir(root, theme)
    manifest = tomllib.loads((tdir / "manifest.toml").read_text(encoding="utf-8"))
    base_css = (tdir / "base.css").read_text(encoding="utf-8")

    env = Environment(
        loader=FileSystemLoader(str(tdir)),
        autoescape=select_autoescape(enabled_extensions=("j2",), default=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["float"] = lambda v: float(v) if str(v).replace(".", "", 1).lstrip("-").isdigit() else 0.0

    body_sections = [s for s in sections if s.get("type") != "cover"]
    known = set(manifest.get("supports", []))
    for s in body_sections:
        if s.get("type") not in known:
            log.warning("section type %r not in theme %r — rendering generic", s.get("type"), theme)

    html = env.get_template("issue.html.j2").render(
        m=masthead,
        counts=counts,
        contents=_contents(body_sections),
        body_sections=body_sections,
        total_pages=len(body_sections) + 1,
        base_css=base_css,
        fonts_href=manifest.get("fonts_href", ""),
        locale=masthead.get("locale", "en"),
    )

    out_dir = out_dir or issue_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "issue.html"
    html_path.write_text(html, encoding="utf-8")
    log.info("rendered HTML → %s", html_path)
    result = {"html": html_path}

    if pdf:
        chrome = _find_chrome()
        if not chrome:
            log.warning("no Chrome found — skipping PDF (set CLEO_CHROME). HTML is ready.")
            return result
        pdf_path = out_dir / "issue.pdf"
        cmd = [
            chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
            "--no-sandbox", f"--print-to-pdf={pdf_path}", html_path.as_uri(),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if pdf_path.exists():
            log.info("rendered PDF → %s", pdf_path)
            result["pdf"] = pdf_path
        else:
            log.error("Chrome did not produce a PDF: %s", proc.stderr[-400:])
    return result

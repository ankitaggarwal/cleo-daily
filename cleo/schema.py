"""The two contracts every part of Cleo speaks.

* ``Item``  — the normalized unit of content. Every source, however exotic,
  is mapped *into* this shape so the Editor reasons over a uniform list.
* ``Issue`` — theme-agnostic structured content the Editor emits. Content
  only, zero styling; the theme decides how each section looks.

These are deliberately permissive (``extra="allow"``, optional fields): a thin
day, a half-built source, or a new section type should never crash the engine.
Honesty over filling applies to the data model too.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Item: the lingua franca ──────────────────────────────────────────────────


class Media(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str = "image"
    url: str


class Item(BaseModel):
    """One piece of raw material, normalized. Output of ``cleo ingest``."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(description="stable dedupe key, sha1(url|title|source)")
    beat: str = Field(description="the lens this came in on, from the source block")
    source: str = Field(description="human-readable origin, e.g. 'Stratechery'")
    title: str
    url: Optional[str] = None
    author: Optional[str] = None
    published: Optional[datetime] = None
    text: str = ""
    media: list[Media] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


# ── Issue: what the Editor emits ─────────────────────────────────────────────

Verdict = Literal["READ", "SKIM", "SKIP", "SAVE"]


class Masthead(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = "Cleo Daily"
    subtitle: str = ""
    issue: str = ""
    dateline: str = ""
    today: str = Field("", description="one-line read on the day's mood")


class Counts(BaseModel):
    """The reader's proof that the reading and the cutting happened."""

    scanned: int = 0
    kept: int = 0
    printed: int = 0


class Section(BaseModel):
    """A single section. ``type`` selects the theme template; the rest is the
    section's content. Open set — unknown types degrade to a generic block."""

    model_config = ConfigDict(extra="allow")
    type: str


class Issue(BaseModel):
    model_config = ConfigDict(extra="allow")
    masthead: Masthead = Field(default_factory=Masthead)
    counts: Counts = Field(default_factory=Counts)
    sections: list[Section] = Field(default_factory=list)

    @classmethod
    def from_json(cls, raw: str | bytes) -> "Issue":
        return cls.model_validate_json(raw)

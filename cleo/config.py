"""Load and resolve the whole publication from ``cleo.toml`` + ``.env``.

One file describes the publication (``cleo.toml``); one file holds the secrets
(``.env``, gitignored). The rule that makes personalization safe:

    a capability runs only if its [features] flag is ON *and* its key is present.

So a half-configured feature degrades to off instead of crashing or printing a
placeholder — the same "honesty over filling" the Editor lives by. Toggle in
``[features]``; paste keys in ``.env``; ``cleo doctor`` shows you what's live.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:  # 3.11+
    import tomllib
except ModuleNotFoundError:  # 3.10
    import tomli as tomllib  # type: ignore


ENV_REF = re.compile(r"^env:([A-Z0-9_]+)$")


# ── feature registry: the one place that defines what's toggleable ───────────
# Each feature = a [features] flag + the env keys it needs to actually run.
# `requires` keys are ALL required; an empty list means "no key needed".

@dataclass(frozen=True)
class Feature:
    key: str
    label: str
    requires: tuple[str, ...] = ()
    note: str = ""


FEATURES: tuple[Feature, ...] = (
    Feature("dedupe", "Dedupe against recent issues", note="no key — recommended on"),
    Feature("images", "Generate line-art illustrations", ("GEMINI_API_KEY",)),
    Feature("weather", "Local weather line", note="open-meteo — no key"),
    Feature("inbox", "Gmail newsletters", ("GMAIL_OAUTH_TOKEN",)),
    Feature("signals", "X / Twitter lists", ("X_BEARER_TOKEN",)),
    Feature("calendar", "Your calendar", ("GOOGLE_CALENDAR_TOKEN",)),
    Feature("cricket", "Scores for the Desk", note="wrap any cricket API — no key"),
    Feature("git", "Commit each edition to the repo", note="uses local git"),
    Feature("email", "Email the finished PDF", ("RESEND_API_KEY", "CLEO_SUBSCRIBERS")),
    Feature("web", "Publish to a web target", ("CLEO_WEB_TARGET",)),
)
FEATURES_BY_KEY = {f.key: f for f in FEATURES}


# ── .env loading (tiny, dependency-free) ─────────────────────────────────────


def load_dotenv(path: Path) -> None:
    """Populate os.environ from a .env file. Existing env vars win (CI / shell
    overrides the file). Supports ``KEY=value``, ``export KEY=value``, ``#``
    comments, and single/double quotes."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


def resolve(value: Any) -> Any:
    """Turn an ``env:NAME`` reference into its value (None if unset). Recurses
    through lists/dicts so source ``args`` can reference secrets too."""
    if isinstance(value, str):
        m = ENV_REF.match(value)
        return os.environ.get(m.group(1)) if m else value
    if isinstance(value, list):
        return [resolve(v) for v in value]
    if isinstance(value, dict):
        return {k: resolve(v) for k, v in value.items()}
    return value


# ── config model ─────────────────────────────────────────────────────────────


@dataclass
class Source:
    beat: str
    server: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    weight: str = "standard"
    enabled: bool = True
    gated_by: Optional[str] = None  # a [features] key, if this is a personal source


@dataclass
class PublishTarget:
    type: str
    options: dict[str, Any] = field(default_factory=dict)
    gated_by: Optional[str] = None


@dataclass
class Config:
    root: Path
    raw: dict[str, Any]
    features: dict[str, bool]

    # ── the switchboard ──
    def on(self, feature: str) -> bool:
        """True only if the flag is set AND every required key is present."""
        if not self.features.get(feature, False):
            return False
        spec = FEATURES_BY_KEY.get(feature)
        if spec and any(not os.environ.get(k) for k in spec.requires):
            return False
        return True

    def missing_keys(self, feature: str) -> list[str]:
        spec = FEATURES_BY_KEY.get(feature)
        if not spec:
            return []
        return [k for k in spec.requires if not os.environ.get(k)]

    # ── sections of cleo.toml ──
    @property
    def publication(self) -> dict[str, Any]:
        return self.raw.get("publication", {})

    @property
    def persona(self) -> dict[str, Any]:
        return self.raw.get("persona", {})

    @property
    def theme(self) -> dict[str, Any]:
        return self.raw.get("theme", {})

    def sources(self, *, active_only: bool = True) -> list[Source]:
        out: list[Source] = []
        for block in self.raw.get("sources", []):
            # split nested args.* TOML keys back into one dict
            args = dict(block.get("args", {}))
            gate = _source_gate(block.get("beat", ""), block.get("server", ""))
            src = Source(
                beat=block.get("beat", ""),
                server=block.get("server", ""),
                tool=block.get("tool", ""),
                args=resolve(args),
                weight=block.get("weight", "standard"),
                enabled=block.get("enabled", True),
                gated_by=gate,
            )
            if active_only and not self._source_active(src):
                continue
            out.append(src)
        return out

    def _source_active(self, src: Source) -> bool:
        if not src.enabled:
            return False
        if src.gated_by and not self.on(src.gated_by):
            return False
        return True

    def publish_targets(self, *, active_only: bool = True) -> list[PublishTarget]:
        out: list[PublishTarget] = []
        for block in self.raw.get("publish", []):
            ttype = block.get("type", "")
            opts = {k: resolve(v) for k, v in block.items() if k != "type"}
            gate = ttype if ttype in FEATURES_BY_KEY else None
            tgt = PublishTarget(type=ttype, options=opts, gated_by=gate)
            if active_only and gate and not self.on(gate):
                continue
            out.append(tgt)
        return out

    # ── image-gen convenience ──
    @property
    def images_enabled(self) -> bool:
        return self.on("images") and self.raw.get("images", {}).get("provider", "none") != "none"

    @classmethod
    def load(cls, root: str | Path = ".") -> "Config":
        root = Path(root).resolve()
        load_dotenv(root / ".env")
        toml_path = root / "cleo.toml"
        if not toml_path.exists():
            raise FileNotFoundError(
                f"no cleo.toml at {toml_path} — run `cleo init` to scaffold one"
            )
        raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        features = {f.key: False for f in FEATURES}
        features.update({k: bool(v) for k, v in raw.get("features", {}).items()})
        return cls(root=root, raw=raw, features=features)


# Map a personal source to the feature flag that gates it. The wide RSS roster
# is always on; the reader's own lenses are opt-in.
_SOURCE_GATES = {
    "inbox": "inbox",
    "signals": "signals",
    "personal": "calendar",
    "calendar": "calendar",
    "weather": "weather",
    "cricket": "cricket",
}


def _source_gate(beat: str, server: str) -> Optional[str]:
    return _SOURCE_GATES.get(beat) or _SOURCE_GATES.get(server)

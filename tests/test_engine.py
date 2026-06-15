"""Stress tests — the engine from many angles.

Covers config + feature gating, the Item/Issue contracts, the RSS adapter's
parsing + robustness, ingest dedupe, and rendering every section type plus the
nasty edges (empty issue, unknown type, zero-valued chart, unicode, one-sided
debate, malformed input). Pure/offline except the network test, which skips
cleanly when there's no connection.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cleo.config import Config
from cleo.render import render
from cleo.schema import Issue, Item
from cleo.sources import rss

REPO = Path(__file__).resolve().parent.parent


# ── config + feature gating ──────────────────────────────────────────────────

def _write_project(tmp: Path, toml: str) -> Path:
    (tmp / "cleo.toml").write_text(toml, encoding="utf-8")
    return tmp


def test_config_missing_toml(tmp_path):
    with pytest.raises(FileNotFoundError):
        Config.load(tmp_path)


def test_feature_off_by_default(tmp_path):
    _write_project(tmp_path, '[publication]\nname="X"\n')
    cfg = Config.load(tmp_path)
    assert cfg.on("images") is False
    assert cfg.on("dedupe") is False


def test_feature_on_but_missing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _write_project(tmp_path, '[publication]\nname="X"\n[features]\nimages=true\n')
    cfg = Config.load(tmp_path)
    assert cfg.on("images") is False                 # flag on, key missing → off
    assert cfg.missing_keys("images") == ["GEMINI_API_KEY"]


def test_feature_on_with_key(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "sk-test")
    _write_project(tmp_path, '[publication]\nname="X"\n[features]\nimages=true\n')
    cfg = Config.load(tmp_path)
    assert cfg.on("images") is True


def test_keyless_feature_just_needs_flag(tmp_path):
    _write_project(tmp_path, '[publication]\nname="X"\n[features]\ndedupe=true\nweather=true\n')
    cfg = Config.load(tmp_path)
    assert cfg.on("dedupe") is True
    assert cfg.on("weather") is True


def test_env_reference_resolution(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_FEEDS", "https://example.com/feed")
    toml = (
        '[publication]\nname="X"\n'
        '[[sources]]\nbeat="x"\nserver="rss"\ntool="fetch_feeds"\n'
        'args.feeds=["env:SECRET_FEEDS"]\n'
    )
    _write_project(tmp_path, toml)
    cfg = Config.load(tmp_path)
    assert cfg.sources()[0].args["feeds"] == ["https://example.com/feed"]


def test_dotenv_loading_and_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv("FROM_FILE", raising=False)
    monkeypatch.setenv("FROM_SHELL", "shell-wins")
    (tmp_path / ".env").write_text('FROM_FILE=file-val\nexport FROM_SHELL="file-loses"\n# c\n')
    _write_project(tmp_path, '[publication]\nname="X"\n')
    Config.load(tmp_path)
    assert os.environ["FROM_FILE"] == "file-val"
    assert os.environ["FROM_SHELL"] == "shell-wins"   # existing env beats the file


def test_personal_source_gated_off(tmp_path):
    toml = (
        '[publication]\nname="X"\n'
        '[[sources]]\nbeat="inbox"\nserver="gmail"\ntool="search"\nenabled=true\n'
    )
    _write_project(tmp_path, toml)
    cfg = Config.load(tmp_path)
    assert cfg.sources(active_only=True) == []        # gated by 'inbox' feature, which is off
    assert len(cfg.sources(active_only=False)) == 1


# ── schema contracts ─────────────────────────────────────────────────────────

def test_item_minimal():
    it = Item(id="a", beat="wire", source="HN", title="t")
    assert it.text == "" and it.media == []


def test_issue_roundtrip_and_extra_fields():
    raw = '{"masthead":{"name":"C"},"sections":[{"type":"one-thing","headline":"h","wild":1}]}'
    issue = Issue.from_json(raw)
    assert issue.sections[0].type == "one-thing"
    assert issue.model_dump()["sections"][0]["wild"] == 1   # extra preserved


def test_issue_empty_defaults():
    issue = Issue()
    assert issue.counts.scanned == 0 and issue.sections == []


# ── rss adapter helpers ──────────────────────────────────────────────────────

@pytest.mark.parametrize("s,ok", [("2d", True), ("36h", True), ("90m", True), ("", False), ("garbage", False), ("5x", False)])
def test_since_cutoff(s, ok):
    assert (rss._since_cutoff(s) is not None) == ok


def test_clean_strips_html_and_truncates():
    assert rss._clean("<p>hello   <b>world</b></p>") == "hello world"
    assert len(rss._clean("<p>" + "x" * 9000 + "</p>", limit=100)) == 100


def test_stable_id_deterministic():
    a = rss._stable_id("u", "t", "s")
    assert a == rss._stable_id("u", "t", "s") and len(a) == 16


# ── ingest dedupe ────────────────────────────────────────────────────────────

def test_ingest_dedupe(monkeypatch, tmp_path):
    from cleo import ingest as ing
    dup = {"id": "same", "beat": "wire", "source": "S", "title": "t"}
    monkeypatch.setattr(ing, "_from_rss", lambda src: [dict(dup), dict(dup)])
    toml = '[publication]\nname="X"\n[[sources]]\nbeat="x"\nserver="rss"\ntool="fetch_feeds"\nargs.feeds=["http://x"]\n'
    (tmp_path / "cleo.toml").write_text(toml)
    cfg = Config.load(tmp_path)
    items = ing.ingest(cfg, tmp_path / "runs" / "d")
    assert len(items) == 1
    assert (tmp_path / "runs" / "d" / "items.jsonl").exists()


def test_ingest_drops_malformed(monkeypatch, tmp_path):
    from cleo import ingest as ing
    monkeypatch.setattr(ing, "_from_rss", lambda src: [{"no": "id-or-required-fields"}])
    toml = '[publication]\nname="X"\n[[sources]]\nbeat="x"\nserver="rss"\ntool="fetch_feeds"\nargs.feeds=["http://x"]\n'
    (tmp_path / "cleo.toml").write_text(toml)
    cfg = Config.load(tmp_path)
    assert ing.ingest(cfg, tmp_path / "runs" / "d") == []


def test_ingest_mcp_without_config_is_graceful(tmp_path):
    toml = (
        '[publication]\nname="X"\n[features]\ninbox=true\n'
        '[[sources]]\nbeat="inbox"\nserver="gmail"\ntool="search"\nenabled=true\n'
    )
    (tmp_path / "cleo.toml").write_text(toml)
    os.environ["GMAIL_OAUTH_TOKEN"] = "t"
    try:
        from cleo import ingest as ing
        cfg = Config.load(tmp_path)
        # 'inbox' is live (flag + key), source active, but no .mcp.json → skip, no crash
        assert ing.ingest(cfg, tmp_path / "runs" / "d") == []
    finally:
        del os.environ["GMAIL_OAUTH_TOKEN"]


# ── rendering: every section + the nasty edges ───────────────────────────────

def _render_issue(tmp_path, issue: dict) -> str:
    p = tmp_path / "issue.json"
    p.write_text(json.dumps(issue), encoding="utf-8")
    res = render(p, root=REPO, theme="broadsheet-mono", out_dir=tmp_path, pdf=False)
    return res["html"].read_text(encoding="utf-8")


def test_render_all_section_types(tmp_path):
    issue = {
        "masthead": {"name": "Cleo Daily", "issue": "No.1", "dateline": "Today", "today": "x"},
        "counts": {"scanned": 100, "kept": 10, "printed": 5},
        "sections": [
            {"type": "one-thing", "headline": "H", "dek": "d", "body": "a\n\nb", "soWhat": "s", "pullQuote": "q", "source": "S"},
            {"type": "brief", "items": [{"headline": "x", "line": "y", "verdict": "READ", "source": "S"}], "cut": "noise"},
            {"type": "deep-dive", "headline": "D", "dek": "d", "body": "p", "evidence": [{"n": "1", "text": "e"}], "source": "S"},
            {"type": "by-numbers", "stat": "9", "caption": "c", "source": "S", "chart": {"series": [{"label": "a", "value": 1}, {"label": "b", "value": 3, "flag": True}]}},
            {"type": "debate", "question": "?", "sideA": {"pos": "p", "arg": "a", "who": "w"}, "sideB": {"pos": "p2", "arg": "a2"}, "mid": "m"},
            {"type": "framework", "name": "F", "explain": "e", "diagram": "<svg></svg>", "applyMonday": "do"},
            {"type": "teardown", "product": "P", "whatsInteresting": "wi", "didWell": ["a", "b"], "steal": "s"},
            {"type": "signals", "items": [{"quote": "q", "who": "w", "source": "S"}]},
            {"type": "margin", "wonder": [{"h": "h", "s": "s", "src": "x"}], "oneGoodIdea": "i", "quote": {"q": "q", "by": "b"}, "tinyJoys": ["j"], "readNext": [{"title": "t", "why": "w"}]},
            {"type": "colophon", "note": "n", "weekAhead": ["mon"], "tomorrow": "t"},
        ],
    }
    html = _render_issue(tmp_path, issue)
    assert "Cleo" in html and "READ" in html and "<svg></svg>" in html
    assert html.count('class="page') == 11      # cover + 10 sections


def test_render_empty_issue_is_just_a_cover(tmp_path):
    html = _render_issue(tmp_path, {"masthead": {"name": "Cleo Daily"}})
    assert html.count('class="page') == 1


def test_render_unknown_section_type_degrades(tmp_path):
    html = _render_issue(tmp_path, {"masthead": {"name": "C"}, "sections": [{"type": "mystery-box", "blob": 1}]})
    assert "generic" in html and "mystery-box" in html


def test_render_zero_valued_chart_no_divzero(tmp_path):
    issue = {"masthead": {"name": "C"}, "sections": [
        {"type": "by-numbers", "stat": "0", "chart": {"series": [{"label": "a", "value": 0}, {"label": "b", "value": 0}]}},
    ]}
    html = _render_issue(tmp_path, issue)   # must not raise ZeroDivisionError
    assert "by-numbers" not in html or "bar" in html


def test_render_one_sided_debate(tmp_path):
    html = _render_issue(tmp_path, {"masthead": {"name": "C"}, "sections": [
        {"type": "debate", "question": "?", "sideA": {"pos": "p", "arg": "a"}},
    ]})
    assert "?" in html


def test_render_unicode_and_html_escaping(tmp_path):
    html = _render_issue(tmp_path, {"masthead": {"name": "C", "today": "日本語 — émoji 🚀 & <script>"}, "sections": []})
    assert "日本語" in html and "🚀" in html
    assert "<script>" not in html          # autoescaped


def test_render_brief_missing_optional_fields(tmp_path):
    html = _render_issue(tmp_path, {"masthead": {"name": "C"}, "sections": [
        {"type": "brief", "items": [{"headline": "only a headline"}]},
    ]})
    assert "only a headline" in html


# ── network (skips offline) ──────────────────────────────────────────────────

@pytest.mark.parametrize("url", ["https://simonwillison.net/atom/everything/"])
def test_rss_live_fetch(url):
    try:
        items = rss.fetch_feeds([url], since="60d", beat="ai-eng", per_feed=2)
    except Exception:
        pytest.skip("no network")
    if not items:
        pytest.skip("feed empty in window")
    assert items[0]["title"] and items[0]["beat"] == "ai-eng"


def test_rss_dead_feed_is_skipped_not_raised():
    # a host that resolves nowhere — must return [] not explode
    assert rss.fetch_feeds(["https://nonexistent.invalid.example/feed"], since="2d") == []

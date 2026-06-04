# Cleo Daily — Architecture

> *"Cleo Daily" is the flagship publication; **`cleo`** is the open-source engine (CLI + skill) that produces it. Other publications are just other configs.*

> An open-source engine for **LLM-authored print magazines**. You declare *sources*, a *persona*, and a *look*; a scheduled Claude Code routine fetches, filters, curates, writes, and lays out a print-ready landscape PDF, then publishes it — on whatever cadence you choose.

This document supersedes `research/architecture-recommendation.md`, which described an earlier, Python-pipeline-centric design. The redesign below is **LLM-driven**, runs on **Claude Code Routines**, and treats **MCP servers as the universal source adapter**.

---

## 1. The core idea

The magazine is not produced by a rigid pipeline. It is produced by an **agent (the Editor)** that runs on a schedule and is given three things:

1. **Sources** — where to pull raw material (MCP servers).
2. **A persona + editorial brief** — who the reader is and what they value.
3. **A look** — a theme that turns structured content into a print-ready page.

Everything deterministic and boring (connecting to MCP, normalizing items, rendering HTML→PDF, emailing) is plain code. Everything that requires *taste* (what to keep, what to cut, what matters, how to say it, what deserves an image) is the **LLM's job**. That split is the whole design.

```
        ┌────────────────────────────────────────────────────────────────┐
        │  RUNTIME:  Claude Code Routine  (scheduled remote agent)         │
        │  one routine = one publication on one cadence (daily / weekly)   │
        └────────────────────────────────────────────────────────────────┘
                                     │ reads
                                     ▼
        cleo.toml  ───────────────────────────────  the whole publication in one file
        (persona · sources · theme · schedule · publish targets · image-gen)

   ┌────────────┐   pull (code)   ┌────────────┐   EDIT (LLM)    ┌────────────┐
   │  SOURCES   │ ──────────────► │   ITEMS    │ ──────────────► │   ISSUE    │
   │ MCP servers│  normalize      │ items.jsonl│ filter·dedup·   │ issue.json │
   │ rss·gmail· │  (cleo.ingest)  │ (one common │ rank·write·     │ (theme-    │
   │ x·bank·... │                 │  schema)    │ pick images     │  agnostic) │
   └────────────┘                 └────────────┘                 └─────┬──────┘
                                                                        │ render (code)
        ┌────────────┐   publish (code)   ┌────────────┐   Chrome       ▼
        │  TARGETS   │ ◄───────────────── │   PDF +    │ ◄──────── theme (HTML/CSS)
        │ file·git·  │                    │  previews  │   headless   + cleo.render
        │ email·web  │                    └────────────┘
        └────────────┘
```

Four contracts are the only things an extender ever touches:

| Contract | What it is | Add one by… |
|---|---|---|
| **Source** | An MCP server exposing tools that return raw content | configuring an MCP server + a `[[sources]]` block |
| **Item** | The normalized unit of content (the lingua franca) | never — it's fixed; adapters map *into* it |
| **Issue** | Theme-agnostic structured content the Editor emits | extend section types in the schema |
| **Theme** | An HTML/CSS package + manifest that renders an Issue | dropping a folder in `themes/` |
| **Publisher** | A small module that ships the artifact | a function in `cleo/publish/` |

---

## 2. Runtime: the Editor routine

A **Claude Code Routine** (`/schedule`) is the engine. There is no separate orchestrator service, no GitHub Actions, no cron-of-Python. The scheduled remote agent *is* the program. Its instructions live in the repo as a skill + `CLAUDE.md`, so the routine is reproducible and versioned.

A run is a single agent turn that executes this loop:

```
1. LOAD     read cleo.toml → persona, beats, theme, targets, cadence window
2. INGEST   for each [[sources]] block: connect to its MCP server, call the
            configured tool(s), collect raw payloads          → (code: cleo ingest)
3. NORMALIZE map every payload into the Item schema, dedupe by url/hash,
            window by date, write runs/<date>/items.jsonl     → (code, LLM assists)
4. EDIT     THE CORE LLM STEP. With the persona brief in context:
              • FILTER   drop noise; this is the anti-distraction promise
              • CLUSTER  merge items about the same thing
              • RANK     order by real reader impact
              • VERDICT  tag items READ / SKIM / SKIP / SAVE
              • WRITE    author every section in the publication's voice,
                         quoting sparingly + always attributing
              • COMMISSION decide which (few) pieces need an image and draft
                         tight, inkjet-friendly prompts
            → emit runs/<date>/issue.json (conforms to the Issue schema)
5. ILLUSTRATE (optional) if an image provider is configured, generate the
            commissioned images under the theme's constraints → assets/
6. RENDER   cleo render issue.json --theme <name>
            → issue.html → Chrome headless → issue.pdf + page PNGs   (code)
7. PUBLISH  for each [[publish]] target: ship it (file / git / email / web)  (code)
8. LOG      append a one-line run record + cost to runs/index.json
```

Steps 1–3, 5–8 are deterministic helpers exposed by the `cleo` CLI and callable as plain Bash by the routine. Step 4 is the agent thinking. This is the **hybrid**: reliable rails, judgment in the middle.

### Why routines (not Actions/cron)
- The thing doing the editorial work is an LLM agent anyway — so the *runtime is also the agent*. No glue process whose only job is to invoke a model.
- Routines carry repo context, MCP connections, secrets, and the skill prompt natively.
- Cadence is a property of the routine (`daily 06:00`, `weekly Mon 07:00`). Two cadences = two routines pointing at two configs.

---

## 3. Configuration: one file describes the whole publication

`cleo.toml` is the single source of truth. A new publication is a new config; the engine is untouched.

```toml
[publication]
name      = "Cleo Daily"
subtitle  = "Field notes for people who build products"
cadence   = "daily"           # daily | weekly | "cron: 0 6 * * *"
locale    = "en"
page      = "11in x 8.5in"    # landscape letter; A4-landscape supported

# WHO this is for — the most important block. The Editor reads this verbatim.
[persona]
reader = """
A product manager drowning in feeds and Slack. Wants signal, not scroll.
Curious beyond work. Values: a sharp 'so what', honest filtering, calm pages.
"""
voice  = "Plain, confident, a little wry. Short sentences. No hype, no listicle filler."
filter = "Cut anything a smart reader could skip with zero regret. Earn every inch."

# LOOK — points at a theme package + the ink/printer constraints
[theme]
name        = "broadsheet-mono"   # folder under themes/
accent      = "#1B5E4F"           # single restrained ink
background  = "white"             # inkjet / ink-tank friendly
images      = "minimal"           # minimal | rich | none  → caps image budget
ink_budget  = "low"               # nudges renderer toward line-art over fills

# IMAGE GENERATION — optional, key-gated. Off unless configured.
[images]
provider = "gemini"               # gemini | none
api_key  = "env:GEMINI_API_KEY"
style    = "single-ink line illustration, white background, no gradients, editorial"
max_per_issue = 3

# SOURCES — each maps an MCP server to a 'beat'. MCP-first: every source is one.
[[sources]]
beat   = "ai-tooling"
server = "rss"                    # an MCP server id from .mcp.json
tool   = "fetch_feeds"
args   = { feeds = ["https://...", "https://..."], since = "2d" }
weight = "lead"                   # hint: lead | standard | margin

[[sources]]
beat   = "signals"
server = "x"                      # Twitter/X MCP — uses your creds
tool   = "home_timeline"
args   = { lists = ["pm-thinkers"], limit = 40 }

[[sources]]
beat   = "inbox"
server = "gmail"
tool   = "search"
args   = { query = "label:newsletters newer_than:2d" }

[[sources]]
beat   = "personal"
server = "calendar"
tool   = "upcoming"
args   = { days = 3 }

# PUBLISH — zero or more targets, run in order
[[publish]]
type = "file"
path = "issues/{date}/"

[[publish]]
type = "git"                      # commit to the archive site repo
message = "Issue {date}"

[[publish]]
type = "email"
server = "resend"                 # an email MCP / provider
to     = ["env:SUBSCRIBERS"]
```

Secrets are referenced as `env:NAME`, never inlined. `.mcp.json` (standard Claude Code MCP config) declares *how* to launch/connect each server; `cleo.toml` declares *what to pull* from it.

---

## 4. Sources — MCP-server-first adapters

**Every source is an MCP server.** This is the single extension mechanism for ingestion, and it leans fully into the Claude ecosystem.

- **Built-in/community servers** cover the common cases: `rss` (feeds, incl. YouTube + Reddit feeds), `gmail`/`imap` (newsletters), `x` (Twitter/X — your credentials), `calendar`, `web` (fetch + extract an arbitrary URL).
- **Personal/sensitive sources** — your bank, your job's internal API, your notes — are just *another MCP server* you point at. The contract is identical; the data never leaves your machine except into your own PDF.
- **Writing a new source = writing (or installing) an MCP server.** No bespoke plugin API to learn. If it speaks MCP, Cleo can read it.

Ingestion is deterministic code (`cleo ingest`): it reads `[[sources]]`, connects to each server via the MCP client, calls the named tool with `args`, and hands raw payloads to normalization. The *only* per-source knowledge Cleo needs is "which tool, which args" — both in config.

### The Item schema (the lingua franca)
Every source, however exotic, is normalized into one shape so the Editor reasons over a uniform list:

```jsonc
{
  "id":        "sha1(url|title|source)",   // stable dedupe key
  "beat":      "ai-tooling",               // from the source block
  "source":    "Anthropic Blog",           // human-readable origin
  "title":     "…",
  "url":       "https://…",                // canonical link, may be null
  "author":    "…",
  "published": "2026-06-01T09:00:00Z",
  "text":      "…",                        // extracted body / transcript / message
  "media":     [{ "type": "image", "url": "…" }],
  "metrics":   { "likes": 0, "amount_usd": 0 },  // optional, source-specific
  "raw":       { }                         // untouched original, for the Editor
}
```

Normalization is mostly mechanical (code) with the LLM available for messy cases (e.g., turning a thread or a transcript into clean `text`). Output: `runs/<date>/items.jsonl`.

---

## 5. The Editor — where taste lives

The single most important step. Input: `items.jsonl` + the `[persona]` brief. Output: a complete `issue.json`. **The Editor's full prompt — including the source roster and the curation doctrine (read 200–400 items, keep ≤1 in 10, span ≥4 lenses, ≥1 non-tech feature) — is `cleo/skill/cleo-editor.md`.** It instructs the Editor to, in order:

1. **Filter** — the anti-distraction core. Discard anything the reader could miss without regret. Be ruthless; an empty section beats a padded one.
2. **Cluster & dedupe** — five outlets, one event → one story, best source kept.
3. **Rank** — by genuine impact on *this* reader, not by recency or virality.
4. **Assign verdicts** — `READ / SKIM / SKIP / SAVE`, surfaced in the layout so the *filtering itself* is the product.
5. **Compose** — write each section in the publication `voice`: a sharp headline, a real "so what", sparing quotes, always attributed with a link. Never reproduce a source's structure wholesale (fair-use + originality).
6. **Commission images** — pick at most `images.max_per_issue` pieces that genuinely benefit, and draft prompts that obey the theme's ink constraints (line art, white ground). Most pages stay text + line-art.

The Editor emits the **Issue schema** — content only, zero styling. Section *types* are an open, extensible set (see §7). The theme decides how each type looks; the Editor decides what each type says.

---

## 6. Rendering — deterministic, theme-driven, print-first

`cleo render issue.json --theme broadsheet-mono`:

1. Validate `issue.json` against the schema.
2. For each section, pick the theme's matching template/partial; unknown types degrade gracefully (rendered as a generic block) and are logged.
3. Generate any data-driven vector art (charts, timelines, the masthead mark) as **inline SVG** — crisp at print DPI, and cheap on ink.
4. Assemble one self-contained HTML doc (fonts subset/embedded), then **Chrome `--headless --print-to-pdf`** at `11in × 8.5in` landscape, margins `0`, page-break rules from the theme. (Reuses the existing `render.sh` / `assemble_creative.py` approach, generalized.)
5. Emit `issue.pdf` + per-page PNG previews for quick review.

**Print/ink constraints are first-class.** Themes default to: white background, one accent ink, no full-bleed fills, line-art and rules instead of photographs, fonts that render well on an ink-tank printer. `images = "minimal"` and `ink_budget = "low"` in config tighten this further. The output is meant to be *printed and read on paper*, away from the screen — that's the point.

---

## 7. The Issue schema (theme-agnostic content)

A growing vocabulary of section types lets the magazine be *more than articles*. The Editor chooses which to populate each issue; themes provide a renderer for each.

```jsonc
{
  "masthead": { "name", "subtitle", "issue", "dateline", "weather": "one-line week-in-mood" },
  "sections": [
    { "type": "one-thing",   "kicker", "headline", "dek", "body", "soWhat", "source" },
    { "type": "brief",       "items": [{ "headline","line","verdict","source","url" }] },
    { "type": "deep-dive",   "headline","dek","body","pullQuote","evidence":[…] },
    { "type": "teardown",    "product","whatsInteresting","didWell":[…],"steal" },
    { "type": "framework",   "name","origin","explain","applyMonday","diagram":"svg-spec" },
    { "type": "by-numbers",  "stat","context","source","chart":{ "kind","series":[…] } },
    { "type": "debate",      "question","sideA":{…},"sideB":{…} },
    { "type": "signals",     "items": [{ "quote","who","handle","source" }] },
    { "type": "field-notes", "recommendations":[{ "kind","title","by","why","url" }] },
    { "type": "margin",      "quote":{…}, "puzzle":{…}, "tinyJoys":[…] },
    { "type": "ship-log",    "calendar":[…],"reminders":[…],"nudge" },
    { "type": "colophon",    "note","howMade","nextIssue" }
  ]
}
```

Adding a section type = (1) document its shape here, (2) add a renderer partial to each theme that wants it. The Editor will use any type the active theme's manifest advertises.

---

## 8. Themes

A theme is a folder under `themes/<name>/`:

```
themes/broadsheet-mono/
  manifest.toml     # name, supported section types, fonts, ink defaults, page size
  base.css          # grid, type scale, print rules (@page, break-inside)
  sections/*.html   # one partial per section type it supports
  marks.py          # optional: inline-SVG generators (masthead, charts, diagrams)
```

The 5 existing designs in `samples/styles/` (standard, signal, atelier, terminal, dispatch) become the first theme library. A theme declares which section types it can render; the Editor is told the active theme's capabilities so it never emits a section the theme can't show.

---

## 9. Publishers

Outputs are small, ordered modules under `cleo/publish/`, each a function `(artifact, config) -> result`:

- `file` — write the PDF + previews to a dated folder.
- `git` — commit to an archive-site repo (GitHub/Cloudflare Pages renders the index + RSS).
- `email` — send via an email MCP/provider (e.g. Resend) to a subscriber list.
- `web` — push to a hosting target.

Adding one is a single function + a `[[publish]]` block. Publishing only ever moves an already-built artifact; it never touches content.

---

## 10. Repository layout

```
README.md           # the front door
LICENSE             # MIT
ARCHITECTURE.md     # this document
cleo.toml           # the publication (persona · sources · theme · publish)
.mcp.json.example   # sample MCP source config (copy → .mcp.json, gitignored)
cleo/
  skill/            # the Editor prompt — the routine's program  ← exists today
    cleo-editor.md
  cli.py            # `cleo init | ingest | edit | render | publish | run`  (roadmap)
  ingest.py         # MCP client: pull + normalize → items.jsonl            (roadmap)
  schema/           # Item, Issue, Theme manifest                           (roadmap)
  render/           # issue.json + theme → html → pdf (Chrome headless)     (roadmap)
  publish/          # file · git · email · web                             (roadmap)
themes/             # broadsheet-mono, … (extracted from the example)       (roadmap)
editions/           # the published magazines: cleo-daily-no-01.pdf (+ .html source)
assets/             # preview images used by the README
runs/<date>/        # generated each run: items.jsonl, issue.json, pdf (gitignored)
```

`pip install cleodaily` → `cleo init` scaffolds `cleo.toml`, `.mcp.json`, a theme, and registers the Editor skill. `cleo run` does one full cycle locally. `/schedule` turns that into the recurring routine.

---

## 11. Failure handling & cost

- **Empty/failed source** → log, skip, continue. A dead feed never blocks an issue.
- **Thin news day** → the Editor is told it may run shorter sections rather than pad. Honesty over volume.
- **Render failure** → previous issue stays live; alert via the same publish channel.
- **Determinism** → ingest/normalize/render/publish are pure code and unit-testable; only the Editor step varies, and it's pinned by the skill prompt + persona.
- **Cost** → one LLM editing pass per issue over a filtered item set. Daily cadence over ~30–60 fresh items (deduped against recent issues) is a few cents to low dollars per issue. Image gen (if on) dominates only when enabled.

---

## 12. What changed from the old design

| Old (`research/architecture-recommendation.md`) | New (this doc) |
|---|---|
| Python pipeline; LLM = batch summarizer | **LLM-driven**; the agent *is* the pipeline |
| Sentence-BERT + FAISS dedup/cluster in code | Editor clusters/filters with judgment |
| GitHub Actions cron | **Claude Code Routines** |
| Hardcoded ingest per source type | **MCP-server-first**; one adapter contract |
| Fixed AI-news structure | Config-driven persona + open section vocabulary |
| Screen/email PDF | **Print-first**, inkjet/ink-tank constraints baked in |

---

*Cleo Daily is designed so that the only things a user edits are `cleo.toml`, `.mcp.json`, and (rarely) a theme — and the only thing a contributor adds is an MCP server, a theme, a section type, or a publisher.*

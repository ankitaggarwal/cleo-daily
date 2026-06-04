<div align="center">

# Cleo Daily

**An open-source engine for LLM-authored print magazines.**
You declare your *sources*, a *persona*, and a *look*. A scheduled Claude Code routine reads hundreds of items each morning, keeps roughly one in ten, writes them up in a voice you can stand, and lays the result out as a print-ready landscape PDF — built white-on-white for an ink-tank printer, so you can read on paper and stop scrolling.

<img src="assets/preview-cover.png" width="78%" alt="Cleo Daily — cover of issue No.1">

*The cure for the feed is a thing that can't scroll back.*

</div>

---

## What it is

Cleo Daily turns a wide, curated set of blogs, newsletters and feeds into a calm, dense, **20-page landscape brief** — once a day, automatically. It was built for one reader (a product manager drowning in tabs) but the engine is general: change the config and it's a different publication.

The core idea is a clean split:

> **Boring, reliable work is code. Work that needs taste is the LLM.**

- Connecting to sources, normalising items, rendering HTML→PDF, publishing — **deterministic code**.
- Deciding what to keep, what to cut, what matters, how to say it, what deserves a picture — **the LLM ("the Editor")**.

There is no separate orchestrator. **The scheduled Claude Code routine *is* the engine.**

## How it works

```
cleo.toml ──▶  ROUTINE (Claude Code, scheduled daily)
  persona        1 LOAD      read persona, beats, theme, targets
  sources        2 INGEST    pull each source over MCP            (code)
  theme          3 NORMALIZE → one Item schema, dedupe, window    (code)
  publish        4 EDIT      filter ≤1-in-10 · cluster · rank ·   (LLM ◀ the heart)
                              write in voice · commission images
                 5 RENDER    issue.json + theme → Chrome → PDF    (code)
                 6 PUBLISH   file · git · email · web             (code)
```

Four contracts are the only things you ever touch:

| Contract | What it is | Add one by… |
|---|---|---|
| **Source** | an MCP server that returns raw content | adding a server + a `[[sources]]` block |
| **Item** | the normalised unit every source maps into | (fixed — adapters map *into* it) |
| **Issue** | theme-agnostic structured content the Editor emits | extending the section vocabulary |
| **Theme** | an HTML/CSS package that renders an Issue to print | dropping a folder in `themes/` |
| **Publisher** | ships the finished artifact | a small function in `cleo/publish/` |

Full design in **[ARCHITECTURE.md](ARCHITECTURE.md)**.

## The Editor's doctrine

The magic isn't aggregation — it's **subtraction**. The Editor prompt ([`cleo/skill/cleo-editor.md`](cleo/skill/cleo-editor.md)) is non-negotiable about it:

- **1-in-10, or stricter.** Read 200–400 items a day; keep ≤10% as candidates; feature only the strongest ~20.
- **Density, not volume.** Every inch carries an idea, a consequence, or a delight — never "this happened."
- **Wide angle, always.** Each issue spans ≥4 lenses and features ≥1 piece from outside tech.
- **Honesty over filling.** A thin day gets a thin issue. Never pad.
- **Originality, not reproduction.** Quote sparingly, attribute always, link to the source — never replace it.

## Sources are MCP servers

Every source is an MCP server — RSS, Gmail, X/Twitter, your calendar, your bank, a cricket feed, or one you write yourself. The default roster (in [`cleo.toml`](cleo.toml)) is a deliberately wide net across six lenses:

> **Strategy** Stratechery · Platformer · Ben Evans · Not Boring · Exponential View · a16z
> **Product** Lenny's · SVPG · Mind the Product · **AI/eng** Import AI · One Useful Thing · Simon Willison · Pragmatic Engineer · MIT Tech Review
> **Wide-angle** Marginal Revolution · Noahpinion · Slow Boring · Astral Codex Ten · Works in Progress · Construction Physics
> **Wire & curiosity** Hacker News · The Verge · Ars Technica · Quanta · Smithsonian · Aeon
> **Yours** Gmail newsletters · an X list · your calendar · cricket · weather

## Quickstart

```bash
# 1. configure
cp .mcp.json.example .mcp.json     # add your MCP servers + secrets
$EDITOR cleo.toml                  # set persona, sources, theme, schedule

# 2. run one issue locally (the routine's loop, by hand)
#    ingest → edit → render → publish
cleo run --date today              # (engine CLI — see ARCHITECTURE.md / roadmap)

# 3. or render an existing issue.json to PDF directly
#    issue.json + theme → self-contained HTML → headless Chrome → PDF
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf=cleo.pdf "file://$PWD/cleo.html"

# 4. schedule it (Claude Code routine, daily)
#    /schedule  →  run the cleo-editor skill every morning
```

> **Status:** the **Editor prompt, config, architecture and a fully-worked example issue are complete**. The `cleo` CLI (deterministic ingest/render/publish around the prompt) is the next build — see the roadmap. Today you can run the loop by pointing a Claude Code routine at `cleo/skill/cleo-editor.md`.

## Editions

Published magazines live in **[`editions/`](editions/)** — open **[`cleo-daily-no-01.pdf`](editions/cleo-daily-no-01.pdf)** (Vol. I, No. 1). It was produced by running the doctrine against the live roster, and it's **consumption-ready**: a widget appears *only* if there's real data behind it. With no live weather or cricket feed connected that morning, the Desk leaves their space empty and says so, rather than printing a placeholder. Each edition's self-contained source HTML sits beside its PDF. Twenty pages:

> Cover · The One Thing · The Brief · From Hacker News · Signals · Deep Dive · Evidence · The Conversation · Spotlight · The Long View · Craft · The Stack · The Metric · Science & Wonder · Then · The Long View II · The Margin · Puzzles · The Desk · Colophon

<div align="center"><img src="assets/preview-interior.png" width="70%" alt="An interior page"></div>

## Design constraints (why it looks like this)

- **Pure white background**, one restrained accent ink — built for ink-tank printers; no wasted toner.
- **No photographs.** Charts, diagrams and marks are inline SVG line-art.
- **Landscape, print-first.** A4/Letter landscape, real margins, page-break rules — made to be printed, folded, and read away from a screen.
- Typeset in Fraunces (display), Source Serif 4 (body), Inter (labels).

## Roadmap

- [ ] `cleo` CLI: `init · ingest · edit · render · publish · run`
- [ ] Package the example's design as the first installable **theme** (`themes/broadsheet-mono/`)
- [ ] Reference MCP servers: `rss` (with feed auto-discovery + a real UA), `gmail`, `x`, `calendar`, `cricket`, `open-meteo`
- [ ] Dedup against the last N issues (the key daily-cadence filter)
- [ ] Optional image generation (Gemini), key-gated, single-ink line illustrations only
- [ ] Print imposition (`--impose`) for saddle-stapled booklets

## Contributing

The four extension points are the contract. To add value you write one of: an **MCP source**, a **theme**, a **section type**, or a **publisher**. Issues and PRs welcome. See [ARCHITECTURE.md](ARCHITECTURE.md) for the shapes.

## License

[MIT](LICENSE). The engine is yours; the sources are theirs (Cleo links and attributes, it doesn't republish); the printer is yours.

---

<div align="center"><sub>Read hundreds. Keep a tenth. Print twenty. Make them wide.</sub></div>

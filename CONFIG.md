# Personalizing Cleo

Everything about your publication lives in **two files**, and the rule between them is simple:

> A feature runs only if its flag in **`cleo.toml`** is **on** *and* its key in **`.env`** is **present**.

So you turn things on in one place, paste secrets in another, and a half-configured feature
quietly stays off instead of crashing or printing a placeholder. `cleo doctor` shows you the
truth at a glance.

```
cleo.toml   ── the publication: who it's for, what to pull, how it looks, what's on
.env        ── the secrets:     one key per line (gitignored, never committed)
```

---

## 1. The switchboard — `cleo.toml [features]`

This is the one place you turn capabilities on and off.

```toml
[features]
dedupe   = true     # dedupe against recent issues — the key daily filter (no key)
weather  = false    # local weather line on the cover                     (no key)
images   = false    # generate single-ink line-art illustrations          (GEMINI_API_KEY)
inbox    = false    # Gmail newsletters                                   (GMAIL_OAUTH_TOKEN)
signals  = false    # an X / Twitter list                                 (X_BEARER_TOKEN)
calendar = false    # your week ahead, for the Desk                       (GOOGLE_CALENDAR_TOKEN)
cricket  = false    # scores for the Desk                                 (wrap any cricket API)
git      = false    # commit each edition to the repo                     (uses local git)
email    = false    # email the finished PDF              (RESEND_API_KEY + CLEO_SUBSCRIBERS)
web      = false    # publish to a web target                             (CLEO_WEB_TARGET)
```

Keyless features (`dedupe`, `weather`, `cricket`, `git`) go live the moment the flag is `true`.
The rest also need their key(s) below.

## 2. The keys — `.env`

```bash
cp .env.example .env
```

Then paste keys for **only** the features you switched on. Leave the rest blank.

```bash
# .env
ANTHROPIC_API_KEY=        # only for `cleo edit` (a routine doesn't need it)
GEMINI_API_KEY=sk-...     # unlocks images
GMAIL_OAUTH_TOKEN=...     # unlocks inbox
RESEND_API_KEY=...        # \ unlock email together
CLEO_SUBSCRIBERS=a@b.com  # /
```

`.env` is gitignored. Existing shell/CI env vars win over the file, so you can override in
deploy without editing it.

## 3. Confirm — `cleo doctor`

```text
Features
  dedupe    ● live          Dedupe against recent issues
  images    ○ on, missing key (GEMINI_API_KEY)   Generate line-art illustrations
  inbox     ○ off           Gmail newsletters

Sources (active)
  ● strategy    rss/fetch_feeds · 6 feed(s)
  ○ inbox       gmail/search · needs 'inbox'
```

`● live` = on and ready. `○ on, missing key` = flag is on but the key is blank. `○ off` = flag off.

---

## Common recipes

**Just the wide RSS roster (zero keys).** The default. `cleo run` works out of the box.

**Add a weather line.** Set `weather = true`, add a source block, no key:

```toml
[[sources]]
beat = "weather"
server = "weather"
tool = "today"
args = { lat = 12.97, lon = 77.59, place = "Bangalore" }
```

**Add your Gmail newsletters.** Set `inbox = true`, paste `GMAIL_OAUTH_TOKEN` in `.env`, and make
sure the `gmail` server is declared in `.mcp.json` (copy from `.mcp.json.example`). The existing
`[[sources]] beat = "inbox"` block turns itself on.

**Email each edition.** Set `email = true`, add `RESEND_API_KEY` + `CLEO_SUBSCRIBERS`, and add:

```toml
[[publish]]
type = "email"
```

**Swap the persona / voice / cadence.** Edit `[persona]`, `[publication]`. A new publication is a
new `cleo.toml` — the engine is untouched.

---

## Where each thing is read

| You edit… | …to change |
|---|---|
| `cleo.toml [features]` | what's on/off |
| `cleo.toml [persona]` | who it's for, the voice, the filter |
| `cleo.toml [[sources]]` | what to pull, and from which MCP server |
| `cleo.toml [theme]` | the look (and which theme folder) |
| `cleo.toml [[publish]]` | where the finished PDF ships |
| `.env` | every secret |
| `.mcp.json` | how each MCP server is launched (copy from the example) |

# Running Cleo as a Claude routine

In production the **routine is the Editor**. A scheduled Claude agent wakes once a day, calls the
deterministic `cleo` helpers for the boring parts, and does the one part that needs taste —
reading, cutting 9-in-10, and writing the issue — itself, by following the skill. No separate
orchestrator, no glue process whose only job is to invoke a model.

## What the routine does each run

```
1. cleo ingest            pull every source over MCP → runs/<date>/items.jsonl   (code)
2. read the skill +       apply the Doctrine: filter, cluster, rank, write in
   items + recent issues  voice, set honest counts → runs/<date>/issue.json      (THE MODEL)
3. cleo render            issue.json + theme → HTML → headless Chrome → PDF       (code)
4. cleo publish           ship to each [[publish]] target                        (code)
```

Step 2 is the whole job, and it is the agent thinking — there is no `cleo edit` call in a routine
(that command exists only for running the loop locally without a routine).

## Set it up

1. **Install + configure** (see [CONFIG.md](../CONFIG.md)):
   ```bash
   uv venv && uv pip install -e '.[dev]'
   cleo init          # scaffolds .env and .mcp.json
   cleo doctor        # confirm sources + features
   ```

2. **Schedule the routine.** Point a daily Claude routine at the Editor skill
   ([`cleo/skill/cleo-editor.md`](../cleo/skill/cleo-editor.md)) with a prompt like:

   > Run today's Cleo Daily. Execute `cleo ingest --date today`. Read
   > `runs/today/items.jsonl` and the last 5 `runs/*/issue.json`. Apply the doctrine in the
   > skill and write `runs/today/issue.json`. Then run `cleo render` and `cleo publish`.

   Cadence is a property of the routine (`daily 06:00`). Two cadences = two routines pointing at
   two configs.

3. **The MCP servers** the routine connects to are declared in `.mcp.json` (copy from
   [`.mcp.json.example`](../.mcp.json.example)). The keystone `rss` and `weather` servers ship in
   [`servers/`](../servers/) and need no keys.

## Why a routine (not Actions / cron)

- The thing doing the editorial work is a model anyway — so the *runtime is also the agent*.
- Routines carry repo context, MCP connections, secrets, and the skill prompt natively.
- A thin day produces a thin issue because a *judgment-capable* agent decided so, not because a
  script padded to fill the page.

## Getting the PDF home

The walkthrough video sends the finished PDF from the cloud routine to a printer at home over
**Tailscale** (cloud → tailnet → the machine wired to the ink-tank printer). Any `[[publish]]`
target works — `file`, `git`, `email`, `web` — but Tailscale is the clean way to reach a printer
that isn't on the public internet.

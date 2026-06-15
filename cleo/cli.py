"""`cleo` — the deterministic plumbing around the Editor.

    cleo doctor                 what's configured, what's live, what's missing
    cleo init                   scaffold .env and .mcp.json from the examples
    cleo ingest                 pull sources over MCP → runs/<date>/items.jsonl
    cleo edit                   run the Editor locally → runs/<date>/issue.json
    cleo render <issue.json>    issue.json + theme → HTML → Chrome → PDF
    cleo publish                ship the built artifact to each [[publish]] target
    cleo run                    the whole loop: ingest → edit → render → publish

In a Claude routine you don't call `edit` — the routine *is* the Editor. It
calls ingest, then writes issue.json by following the skill, then render/publish.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import logging
import sys
from pathlib import Path

from .config import FEATURES, Config


def _today() -> str:
    return _dt.date.today().isoformat()


def _run_dir(cfg: Config, date: str) -> Path:
    return cfg.root / "runs" / date


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)-7s %(name)s: %(message)s",
    )


# ── commands ─────────────────────────────────────────────────────────────────

GREEN, DIM, BOLD, RED, RESET = "\033[32m", "\033[2m", "\033[1m", "\033[31m", "\033[0m"


def cmd_doctor(cfg: Config, args) -> int:
    print(f"\n{BOLD}{cfg.publication.get('name', 'Cleo')}{RESET} — {cfg.publication.get('cadence','daily')}\n")

    print(f"{BOLD}Features{RESET}")
    for f in FEATURES:
        flag = cfg.features.get(f.key, False)
        live = cfg.on(f.key)
        if live:
            badge = f"{GREEN}● live{RESET}"
        elif flag and not live:
            missing = ", ".join(cfg.missing_keys(f.key))
            badge = f"{RED}○ on, missing key{RESET} {DIM}({missing}){RESET}"
        else:
            badge = f"{DIM}○ off{RESET}"
        print(f"  {f.key:<9} {badge}  {DIM}{f.label}{RESET}")

    print(f"\n{BOLD}Sources{RESET} (active)")
    for s in cfg.sources(active_only=True):
        n = len(s.args.get("feeds", [])) if s.server == "rss" else 1
        print(f"  {GREEN}●{RESET} {s.beat:<11} {DIM}{s.server}/{s.tool} · {n} feed(s){RESET}")
    inactive = [s for s in cfg.sources(active_only=False) if s not in cfg.sources(active_only=True)]
    for s in inactive:
        why = f"needs '{s.gated_by}'" if s.gated_by else "disabled"
        print(f"  {DIM}○ {s.beat:<11} {s.server}/{s.tool} · {why}{RESET}")

    print(f"\n{BOLD}Publish{RESET}")
    for t in cfg.publish_targets(active_only=False):
        live = (not t.gated_by) or cfg.on(t.gated_by)
        dot = f"{GREEN}●{RESET}" if live else f"{DIM}○{RESET}"
        print(f"  {dot} {t.type}")

    editor_key = "ANTHROPIC_API_KEY" in __import__("os").environ
    print(f"\n{BOLD}Editor (local){RESET}  {GREEN+'● key set' if editor_key else DIM+'○ no key (routine runs the Editor)'}{RESET}")
    print(f"{DIM}Toggle features in cleo.toml [features]; paste keys in .env.{RESET}\n")
    return 0


def cmd_init(cfg_root: Path, args) -> int:
    for example in (".env", ".mcp.json"):
        src = cfg_root / f"{example}.example"
        dst = cfg_root / example
        if not src.exists():
            print(f"  {DIM}no {src.name}{RESET}")
            continue
        if dst.exists():
            print(f"  {DIM}{dst.name} exists — left alone{RESET}")
            continue
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"  {GREEN}created{RESET} {dst.name}  {DIM}(edit it){RESET}")
    print(f"\nNext: edit cleo.toml [features], paste keys in .env, then `cleo doctor`.")
    return 0


def cmd_ingest(cfg: Config, args) -> int:
    from .ingest import ingest
    items = ingest(cfg, _run_dir(cfg, args.date))
    print(f"{GREEN}ingested{RESET} {len(items)} items → runs/{args.date}/items.jsonl")
    return 0


def cmd_edit(cfg: Config, args) -> int:
    from .edit import edit
    from .schema import Item
    run = _run_dir(cfg, args.date)
    items_path = run / "items.jsonl"
    if not items_path.exists():
        print(f"{RED}no items.jsonl — run `cleo ingest` first{RESET}", file=sys.stderr)
        return 1
    items = [Item.model_validate_json(l) for l in items_path.read_text().splitlines() if l.strip()]
    issue = edit(cfg, items)
    out = run / "issue.json"
    out.write_text(issue.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
    print(f"{GREEN}edited{RESET} {issue.counts.printed} printed / {issue.counts.kept} kept → {out}")
    return 0


def cmd_render(cfg: Config, args) -> int:
    from .render import render
    issue_path = Path(args.issue) if args.issue else _run_dir(cfg, args.date) / "issue.json"
    if not issue_path.exists():
        print(f"{RED}no issue.json at {issue_path}{RESET}", file=sys.stderr)
        return 1
    theme = args.theme or cfg.theme.get("name", "broadsheet-mono")
    res = render(issue_path, root=cfg.root, theme=theme, pdf=not args.no_pdf)
    for k, v in res.items():
        print(f"{GREEN}{k}{RESET} → {v}")
    return 0


def cmd_publish(cfg: Config, args) -> int:
    from .publish import publish
    run = _run_dir(cfg, args.date)
    artifact = {k: run / f"issue.{k}" for k in ("pdf", "html") if (run / f"issue.{k}").exists()}
    if not artifact:
        print(f"{RED}nothing to publish — run `cleo render` first{RESET}", file=sys.stderr)
        return 1
    for r in publish(cfg, artifact):
        print(f"{GREEN}published{RESET} {r}")
    return 0


def cmd_run(cfg: Config, args) -> int:
    from .ingest import ingest
    from .render import render
    from .publish import publish

    run = _run_dir(cfg, args.date)
    items = ingest(cfg, run)
    print(f"{GREEN}ingested{RESET} {len(items)} items")

    if args.no_edit:
        print(f"{DIM}--no-edit: stopping. A routine writes issue.json from the skill.{RESET}")
        return 0
    from .edit import edit
    issue = edit(cfg, items)
    (run / "issue.json").write_text(issue.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
    print(f"{GREEN}edited{RESET} {issue.counts.printed} printed")

    theme = cfg.theme.get("name", "broadsheet-mono")
    res = render(run / "issue.json", root=cfg.root, theme=theme)
    print(f"{GREEN}rendered{RESET} {res.get('pdf', res.get('html'))}")
    for r in publish(cfg, res):
        print(f"{GREEN}published{RESET} {r}")
    return 0


# ── argparse ─────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cleo", description="LLM-authored print magazines.")
    p.add_argument("-C", "--root", default=".", help="project root (has cleo.toml)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="show what's configured and live")
    sub.add_parser("init", help="scaffold .env and .mcp.json")

    for name, help_ in [("ingest", "pull sources"), ("edit", "run the Editor locally"), ("publish", "ship the artifact")]:
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--date", default=_today())

    sp = sub.add_parser("render", help="issue.json → PDF")
    sp.add_argument("issue", nargs="?", help="path to issue.json (default: runs/<date>/issue.json)")
    sp.add_argument("--date", default=_today())
    sp.add_argument("--theme")
    sp.add_argument("--no-pdf", action="store_true", help="HTML only, skip Chrome")

    sp = sub.add_parser("run", help="ingest → edit → render → publish")
    sp.add_argument("--date", default=_today())
    sp.add_argument("--no-edit", action="store_true", help="stop after ingest (a routine edits)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)
    root = Path(args.root)

    if args.cmd == "init":
        return cmd_init(root, args)

    try:
        cfg = Config.load(root)
    except FileNotFoundError as exc:
        print(f"{RED}{exc}{RESET}", file=sys.stderr)
        return 1

    return {
        "doctor": cmd_doctor, "ingest": cmd_ingest, "edit": cmd_edit,
        "render": cmd_render, "publish": cmd_publish, "run": cmd_run,
    }[args.cmd](cfg, args)


if __name__ == "__main__":
    raise SystemExit(main())

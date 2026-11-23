"""The `lab` command.

uv run lab doctor                       is this machine ready?
uv run lab ask "question"               one call through the lab, logged
uv run lab ask --file doc.txt "q"       ask about a document
uv run lab last                         the last line of the log, in full
uv run lab report                       every call so far, summarised
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.json import JSON
from rich.table import Table

from . import doctor, log, report
from .call import call
from .config import ConfigError, load_config
from .providers import ProviderError

console = Console(highlight=False)
MARK = {doctor.OK: "[green]✓[/]", doctor.WARN: "[yellow]![/]", doctor.FAIL: "[red]✗[/]"}

DOC_PROMPT = "Here is a document.\n\n<document>\n{doc}</document>\n\n{question}"


def seconds(ms: float | None) -> str:
    if ms is None:
        return "—"
    return f"{ms / 1000:.1f} s" if ms >= 1000 else f"{ms:.0f} ms"


def money(usd: float | None) -> str:
    if usd is None:
        return "no price"
    return "$0" if usd == 0 else f"${usd:.4f}"


def parse_tags(pairs: list[str]) -> dict[str, str]:
    out = {}
    for p in pairs:
        k, sep, v = p.partition("=")
        if not sep:
            raise SystemExit(f"--tag needs key=value, got {p!r}")
        out[k] = v
    return out


def cmd_doctor(args, config) -> int:
    checks = doctor.run(config)
    for c in checks:
        console.print(f" {MARK[c.status]} [bold]{c.name:<9}[/] {c.detail}")
    failed = sum(c.status == doctor.FAIL for c in checks)
    console.print()
    if failed:
        console.print(f"[red]{failed} problem(s) to fix before running experiments.[/]")
        return 1
    console.print("[green]Lab ready.[/]")
    return 0


def cmd_ask(args, config) -> int:
    prompt = args.question
    if args.file:
        prompt = DOC_PROMPT.format(doc=Path(args.file).read_text(encoding="utf-8"), question=prompt)
    tags = parse_tags(args.tag)
    if args.file:
        tags.setdefault("file", Path(args.file).name)
    try:
        res = call(
            prompt,
            system=args.system,
            config=config,
            log_path=args.log,
            write_log=not args.no_log,
            component="cli",
            tags=tags,
            provider=args.provider,
            model=args.model,
            temperature=args.temperature,
            num_ctx=args.num_ctx,
            max_tokens=args.max_tokens,
        )
    except ProviderError as e:
        console.print(f"[red]{e}[/]")
        return 1
    r = res.record
    console.print(res.text.strip())
    console.print()
    sent = ""
    if r["tokens_sent"] is not None:
        sent = f" (sent {'' if r['tokens_sent_exact'] else '~'}{r['tokens_sent']:,})"
    console.print(
        f"[dim]{r['model']} · read {r['tokens_read']:,} tokens{sent} · wrote "
        f"{r['output_tokens']:,} · first token {seconds(r['ttft_ms'])} · total "
        f"{seconds(r['latency_ms'])} · {money(r['cost_usd'])}"
        + ("" if args.no_log else f" · logged {r['run_id'][-6:]}")
        + "[/]"
    )
    for w in res.warnings:
        console.print(f"[bold yellow]⚠ {w['code']}:[/] [yellow]{w['message']}[/]")
    return 0


def cmd_last(args, config) -> int:
    records, _ = log.read(args.log or config.log_path)
    if not records:
        console.print('The log is empty. Run `uv run lab ask "..."` first.')
        return 1
    console.print(JSON(json.dumps(records[-1], ensure_ascii=False)))
    return 0


def cmd_report(args, config) -> int:
    path = args.log or config.log_path
    records, bad = log.read(path)
    filters = parse_tags(args.tag)
    records = [r for r in records if report.matches(r, filters)]
    if not records:
        console.print(f"No calls in {path}.")
        return 1
    rows = report.summarise(records)
    t = Table(title=f"{len(records):,} calls · {path.name}", title_justify="left")
    for col, just in [
        ("model", "left"),
        ("calls", "right"),
        ("tokens read", "right"),
        ("written", "right"),
        ("first token p50", "right"),
        ("total p50", "right"),
        ("total p95", "right"),
        ("slowest", "right"),
        ("cost", "right"),
        ("warnings", "right"),
    ]:
        t.add_column(col, justify=just)
    for row in rows:
        t.add_row(
            row["model"],
            f"{row['calls']:,}",
            f"{row['tokens_read']:,}",
            f"{row['tokens_written']:,}",
            seconds(row["ttft_p50_ms"]),
            seconds(row["latency_p50_ms"]),
            seconds(row["latency_p95_ms"]),
            seconds(row["latency_max_ms"]),
            money(row["cost_usd"])
            + (f" +{row['unpriced_calls']} unpriced" * bool(row["unpriced_calls"])),
            f"[yellow]{row['warnings']}[/]" if row["warnings"] else "0",
        )
    console.print(t)
    warned = report.warning_lines(records)
    if warned:
        console.print("\n[bold]Warnings[/]")
        for r, w in warned[-args.warnings :]:
            console.print(f" [yellow]⚠ {w['code']}[/] [dim]{r['run_id'][-6:]}[/] {w['message']}")
    if bad:
        console.print(f"\n[yellow]{bad} unreadable line(s) skipped.[/]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lab", description="Run, log and measure model calls.")
    p.add_argument("--config", type=Path, help="path to lab.toml (default: nearest one)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="check this machine is ready")

    a = sub.add_parser("ask", help="send one question through the lab")
    a.add_argument("question")
    a.add_argument("--file", help="a document to ask about")
    a.add_argument("--system", help="a system prompt")
    a.add_argument("--provider", choices=["ollama", "anthropic"])
    a.add_argument("--model")
    a.add_argument("--temperature", type=float)
    a.add_argument("--num-ctx", type=int, help="window size in tokens (Ollama)")
    a.add_argument("--max-tokens", type=int)
    a.add_argument("--tag", action="append", default=[], metavar="KEY=VALUE")
    a.add_argument("--log", type=Path, help="log file (default: from lab.toml)")
    a.add_argument("--no-log", action="store_true", help="don't write this call down")

    last = sub.add_parser("last", help="print the last logged call in full")
    last.add_argument("--log", type=Path)

    r = sub.add_parser("report", help="summarise the log")
    r.add_argument("--log", type=Path)
    r.add_argument("--tag", action="append", default=[], metavar="KEY=VALUE")
    r.add_argument("--warnings", type=int, default=5, help="how many recent warnings to list")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        handler = {"doctor": cmd_doctor, "ask": cmd_ask, "last": cmd_last, "report": cmd_report}
        return handler[args.cmd](args, config)
    except ConfigError as e:
        console.print(f"[red]lab.toml: {e}[/]")
        return 2


if __name__ == "__main__":
    sys.exit(main())

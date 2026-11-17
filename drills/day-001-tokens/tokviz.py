#!/usr/bin/env python3
"""tokviz — measure what your text actually costs, in tokens.

Three tokenizers, three distinct roles:

    messages.count_tokens   ground truth for Claude. Model-specific. Never skip.
    HF AutoTokenizer        ground truth for the local model, and the only one
                            here that hands you token boundaries to look at.
    tiktoken                the folklore estimator, under test. Not for costing.

Usage (from the repo root):
    uv run python drills/day-001-tokens/tokviz.py drills/day-001-tokens/samples/*
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pricing  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.text import Text  # noqa: E402

REPO_ROOT = HERE.parents[1]
DEFAULT_COSTS_LOG = REPO_ROOT / "costs.jsonl"

DEFAULT_CLAUDE_MODELS = ["claude-opus-5", "claude-sonnet-5"]
DEFAULT_LOCAL_MODEL = os.environ.get("LOCAL_TOKENIZER", "qwen2.5:7b-instruct")
DEFAULT_TIKTOKEN = "o200k_base"

# Ollama tags are not HuggingFace repo ids. Ollama ships GGUF weights with the
# tokenizer baked into the blob; transformers cannot read that store. The
# tokenizer is byte-identical to the upstream HF repo, so map tag -> repo and
# the counts still describe the model you actually run locally.
OLLAMA_TO_HF = {
    "qwen2.5:7b-instruct": "Qwen/Qwen2.5-7B-Instruct",
    "qwen2.5:7b": "Qwen/Qwen2.5-7B",
    "llama3.1:latest": "meta-llama/Llama-3.1-8B-Instruct",
    "llama3.1:8b": "meta-llama/Llama-3.1-8B-Instruct",
    "llama3.2:latest": "meta-llama/Llama-3.2-3B-Instruct",
    "llama3.2:3b": "meta-llama/Llama-3.2-3B-Instruct",
}


def resolve_local_model(name: str) -> str:
    """Accept either a HF repo id or an Ollama tag."""
    if "/" in name:  # already a HF repo id
        return name
    key = name if ":" in name else f"{name}:latest"
    hf = OLLAMA_TO_HF.get(key)
    if hf:
        console.print(f"[dim]local tokenizer: ollama {key} → HF {hf}[/dim]")
        return hf
    return name


# Haiku 4.5 rejects output_config.effort; only the 5-family accepts it.
EFFORT_MODELS = {"claude-opus-5", "claude-sonnet-5"}

console = Console()


# ---------------------------------------------------------------- run identity


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ulid() -> str:
    """A sortable run id. Day 111 correlates these with OTel trace ids."""
    v = (int(time.time() * 1000) << 80) | secrets.randbits(80)
    return "".join(_CROCKFORD[(v >> (5 * i)) & 31] for i in range(25, -1, -1))


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# --------------------------------------------------------------- measurements


@dataclass
class Measure:
    label: str  # display name of the tokenizer
    kind: str  # "claude" | "local" | "tiktoken"
    tokens: int
    model_id: str | None = None
    is_ground_truth: bool = False


@dataclass
class FileReport:
    path: Path
    text: str
    data: bytes
    measures: list[Measure] = field(default_factory=list)

    @property
    def n_chars(self) -> int:
        return len(self.text)

    @property
    def n_bytes(self) -> int:
        return len(self.data)

    def by_kind(self, kind: str, model_id: str | None = None) -> Measure | None:
        for m in self.measures:
            if m.kind == kind and (model_id is None or m.model_id == model_id):
                return m
        return None

    @property
    def ground_truth(self) -> Measure:
        return next(m for m in self.measures if m.is_ground_truth)


# ------------------------------------------------------------------ counters


class ClaudeCounter:
    """count_tokens, plus the message-envelope correction.

    count_tokens prices a whole *request*, not a string: role framing and a
    small system preamble are included. That overhead is constant, so we
    measure it once per model and subtract it, giving a clean per-text count.
    Use --raw-claude to see the uncorrected request-level numbers instead.
    """

    def __init__(self, client, models: list[str], correct_envelope: bool = True):
        self.client = client
        self.models = models
        self.correct = correct_envelope
        self.envelope: dict[str, int] = {}

    def _envelope_for(self, model: str) -> int:
        if model not in self.envelope:
            # "x" is a single token for every Claude tokenizer; whatever is left
            # over is the per-request framing.
            n = self._count(model, "x")
            self.envelope[model] = max(n - 1, 0)
        return self.envelope[model]

    def _count(self, model: str, text: str) -> int:
        resp = self.client.messages.count_tokens(
            model=model,
            messages=[{"role": "user", "content": text}],
        )
        return resp.input_tokens

    def count(self, model: str, text: str) -> int:
        n = self._count(model, text)
        if self.correct:
            n -= self._envelope_for(model)
        return n


def local_tokenizer(model_name: str):
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")  # silences the PyTorch notice
    try:
        from transformers import AutoTokenizer
    except ImportError:
        console.print("[yellow]transformers not installed; skipping the local tokenizer.[/yellow]")
        return None

    repo = resolve_local_model(model_name)
    try:
        return AutoTokenizer.from_pretrained(repo)
    except Exception as exc:  # gated repo, no network, unmapped tag
        console.print(
            f"[yellow]Local tokenizer {repo!r} unavailable: {exc}[/yellow]\n"
            "[yellow]If you passed an Ollama tag, add it to OLLAMA_TO_HF or use a HF id.\n"
            "  gated (needs `hf auth login` + accepted terms): meta-llama/Llama-3.1-8B\n"
            "  ungated: Qwen/Qwen2.5-7B-Instruct, openai-community/gpt2[/yellow]"
        )
        return None


def tiktoken_encoding(name: str):
    import tiktoken

    return tiktoken.get_encoding(name)


# ------------------------------------------------------- boundary visualization


ALT_STYLES = ["black on #8ec8ff", "black on #ffd28e"]
SPLIT_STYLE = "bold white on red3"


def utf8_split_offsets(data: bytes, token_byte_lengths: list[int]) -> list[int]:
    """Byte offsets where a token boundary lands *inside* a UTF-8 character.

    A continuation byte (0b10xxxxxx) at a token boundary means the previous
    token ended mid-character. This is exact, not a heuristic.
    """
    splits: list[int] = []
    off = 0
    for n in token_byte_lengths[:-1]:
        off += n
        if off < len(data) and (data[off] & 0xC0) == 0x80:
            splits.append(off)
    return splits


def char_at_byte(data: bytes, off: int) -> tuple[str, int]:
    """The character containing byte `off`, and its start byte offset."""
    start = off
    while start > 0 and (data[start] & 0xC0) == 0x80:
        start -= 1
    end = start + 1
    while end < len(data) and (data[end] & 0xC0) == 0x80:
        end += 1
    return data[start:end].decode("utf-8", errors="replace"), start


def viz_tiktoken(text: str, enc, title: str) -> None:
    ids = enc.encode(text)
    pieces = [enc.decode_single_token_bytes(t) for t in ids]

    out = Text()
    for i, raw in enumerate(pieces):
        # The gotcha: a single byte-level BPE token need not be valid UTF-8.
        piece = raw.decode("utf-8", errors="replace")
        broken = "\ufffd" in piece
        style = SPLIT_STYLE if broken else ALT_STYLES[i % 2]
        out.append(piece.replace("\n", "⏎\n"), style=style)

    console.print(f"\n[bold]{title}[/bold]  ({len(ids)} tokens)")
    console.print(out)

    data = text.encode("utf-8")
    splits = utf8_split_offsets(data, [len(p) for p in pieces])
    report_splits(data, splits, len(ids))


def viz_local(text: str, tok, title: str) -> None:
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    ids = enc["input_ids"]
    offsets = enc["offset_mapping"]

    # A character covered by more than one token span is a character the
    # tokenizer tore apart.
    coverage: dict[int, int] = {}
    for s, e in offsets:
        for c in range(s, e):
            coverage[c] = coverage.get(c, 0) + 1
    torn = {c for c, n in coverage.items() if n > 1}

    out = Text()
    printed_to = 0
    for i, (s, e) in enumerate(offsets):
        # Spans of a torn character overlap; print each character only once.
        piece = text[max(s, printed_to) : e]
        printed_to = max(printed_to, e)
        broken = any(c in torn for c in range(s, e))
        style = SPLIT_STYLE if broken else ALT_STYLES[i % 2]
        out.append(piece.replace("\n", "⏎\n"), style=style)

    console.print(f"\n[bold]{title}[/bold]  ({len(ids)} tokens)")
    console.print(out)

    if torn:
        sample = sorted(torn)[:12]
        chars = "".join(sorted({text[c] for c in sample}))
        console.print(
            f"[red]{len(torn)} character(s) spread across multiple tokens[/red] "
            f"— e.g. {chars!r} at char offsets {sample}"
        )
    else:
        console.print("[green]No character split across tokens.[/green]")


def report_splits(data: bytes, splits: list[int], n_tokens: int) -> None:
    if not splits:
        console.print("[green]No token boundary fell inside a UTF-8 character.[/green]")
        return
    seen: dict[int, str] = {}
    for off in splits:
        ch, start = char_at_byte(data, off)
        seen[start] = ch
    shown = list(seen.items())[:12]
    console.print(
        f"[red]{len(splits)} token boundary(ies) land mid-character[/red] "
        f"across {len(seen)} character(s) of {n_tokens} tokens."
    )
    console.print(
        "  "
        + ", ".join(f"{ch!r}@byte{start}" for start, ch in shown)
        + (" …" if len(seen) > len(shown) else "")
    )


# ---------------------------------------------------------------- cost logging


def append_cost(record: dict, path: Path) -> None:
    """Append-only. One line per model call. Never rewritten."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def make_call(client, model: str, text: str, max_tokens: int) -> dict:
    """One real, streamed call. Streaming so ttft_ms is a measured number."""
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "system": "Reply with one short sentence. No preamble.",
        "messages": [
            {"role": "user", "content": f"Summarise this input in one sentence:\n\n{text}"}
        ],
    }
    if model in EFFORT_MODELS:
        kwargs["output_config"] = {"effort": "low"}

    t0 = time.perf_counter()
    ttft_ms: float | None = None
    with client.messages.stream(**kwargs) as stream:
        for event in stream:
            if ttft_ms is None and event.type == "content_block_delta":
                ttft_ms = (time.perf_counter() - t0) * 1000
        msg = stream.get_final_message()
    latency_ms = (time.perf_counter() - t0) * 1000

    u = msg.usage
    return {
        "input_tokens": u.input_tokens or 0,
        "output_tokens": u.output_tokens or 0,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        "ttft_ms": round(ttft_ms) if ttft_ms is not None else None,
        "latency_ms": round(latency_ms),
    }


# ---------------------------------------------------------------------- render


def pct(new: float, base: float) -> float:
    return ((new - base) / base * 100) if base else 0.0


def render_main(reports: list[FileReport], primary: str, assume_output: int, on: date) -> None:
    in_rate, out_rate = pricing.rate(primary).on(on)

    t = Table(title=f"Per file, per tokenizer  ·  ground truth = {primary}")
    t.add_column("file", style="bold")
    t.add_column("chars", justify="right")
    t.add_column("bytes", justify="right")
    t.add_column("tokenizer")
    t.add_column("tokens", justify="right")
    t.add_column("chars/tok", justify="right")
    t.add_column("tok/char", justify="right")
    t.add_column("Δ vs GT", justify="right")
    t.add_column("in $", justify="right")
    t.add_column(f"out $ (+{assume_output})", justify="right")

    for r in reports:
        gt = r.ground_truth.tokens
        for i, m in enumerate(r.measures):
            delta = "— (GT)" if m.is_ground_truth else f"{pct(m.tokens, gt):+.1f}%"
            if m.kind == "claude":
                ci, co = pricing.rate(m.model_id).on(on)
                in_cost = m.tokens * ci / 1e6
                out_cost = assume_output * co / 1e6
                out_s = f"${out_cost:.5f}"
            else:
                # Priced at the ground-truth model's rate: this is the dollar
                # size of the estimation error, not a real quote.
                in_cost = m.tokens * in_rate / 1e6
                out_s = "—"
            t.add_row(
                r.path.name if i == 0 else "",
                f"{r.n_chars:,}" if i == 0 else "",
                f"{r.n_bytes:,}" if i == 0 else "",
                m.label,
                f"{m.tokens:,}",
                f"{r.n_chars / m.tokens:.2f}" if m.tokens else "—",
                f"{m.tokens / r.n_chars:.3f}" if r.n_chars else "—",
                delta,
                f"${in_cost:.5f}",
                out_s,
            )
        t.add_section()

    console.print(t)


def render_summary(reports: list[FileReport], models: list[str]) -> None:
    primary, *rest = models
    other = rest[0] if rest else None

    t = Table(title="The four numbers")
    t.add_column("file", style="bold")
    t.add_column("bytes/char", justify="right")
    t.add_column(f"chars/tok ({primary})", justify="right")
    if other:
        t.add_column("cross-model Δ", justify="right")
    t.add_column("tiktoken error", justify="right")

    for r in reports:
        gt = r.ground_truth.tokens
        row = [
            r.path.name,
            f"{r.n_bytes / r.n_chars:.2f}" if r.n_chars else "—",
            f"{r.n_chars / gt:.2f}" if gt else "—",
        ]
        if other:
            m = r.by_kind("claude", other)
            row.append(f"{pct(m.tokens, gt):+.1f}%" if m else "—")
        tk = r.by_kind("tiktoken")
        row.append(f"{pct(tk.tokens, gt):+.1f}%" if tk else "—")
        t.add_row(*row)

    console.print(t)


# ------------------------------------------------------------------------ main


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("files", nargs="+", type=Path)
    p.add_argument(
        "--models",
        default=",".join(DEFAULT_CLAUDE_MODELS),
        help="comma-separated Claude model ids; the first is ground truth",
    )
    p.add_argument("--local-model", default=DEFAULT_LOCAL_MODEL)
    p.add_argument("--tiktoken-encoding", default=DEFAULT_TIKTOKEN)
    p.add_argument(
        "--raw-claude", action="store_true", help="do not subtract the per-request message envelope"
    )
    p.add_argument(
        "--assume-output",
        type=int,
        default=500,
        help="output tokens assumed for the output-cost estimate",
    )
    p.add_argument("--viz", choices=["none", "tiktoken", "local", "both"], default="none")
    p.add_argument(
        "--viz-chars",
        type=int,
        default=280,
        help="how many leading characters to visualize (0 = all)",
    )
    p.add_argument("--viz-file", default=None, help="only visualize this filename")
    p.add_argument(
        "--call",
        action="store_true",
        help="make one real (billed) streamed call per file and log it",
    )
    p.add_argument("--call-model", default="claude-opus-5")
    p.add_argument("--call-max-tokens", type=int, default=200)
    p.add_argument("--costs-log", type=Path, default=DEFAULT_COSTS_LOG)
    p.add_argument("--run-id", default=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    today = date.today()
    run_id = args.run_id or ulid()

    for w in pricing.expiring_soon():
        console.print(f"[yellow]!! {w}[/yellow]")
    console.print(
        f"[dim]pricing last_verified {pricing.LAST_VERIFIED} "
        f"({pricing.stale_days()}d ago) · run_id {run_id}[/dim]\n"
    )

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        console.print(
            "[red]ANTHROPIC_API_KEY is not set.[/red] Copy .env.example to .env in the repo "
            "root and add your key (token counting is free, but it needs a key)."
        )
        return 2

    from anthropic import Anthropic

    client = Anthropic()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    counter = ClaudeCounter(client, models, correct_envelope=not args.raw_claude)
    tok = local_tokenizer(args.local_model)
    enc = tiktoken_encoding(args.tiktoken_encoding)

    reports: list[FileReport] = []
    for path in args.files:
        if not path.is_file():
            console.print(f"[yellow]skipping {path} (not a file)[/yellow]")
            continue
        data = path.read_bytes()
        text = data.decode("utf-8")
        r = FileReport(path=path, text=text, data=data)

        for i, model in enumerate(models):
            r.measures.append(
                Measure(
                    label=model,
                    kind="claude",
                    model_id=model,
                    tokens=counter.count(model, text),
                    is_ground_truth=(i == 0),
                )
            )
        if tok is not None:
            n = len(tok(text, add_special_tokens=False)["input_ids"])
            r.measures.append(
                Measure(label=f"local:{args.local_model.split('/')[-1]}", kind="local", tokens=n)
            )
        r.measures.append(
            Measure(
                label=f"tiktoken:{args.tiktoken_encoding}",
                kind="tiktoken",
                tokens=len(enc.encode(text)),
            )
        )
        reports.append(r)

    if not reports:
        console.print("[red]No readable files.[/red]")
        return 1

    render_main(reports, models[0], args.assume_output, today)
    console.print()
    render_summary(reports, models)

    if not args.raw_claude and counter.envelope:
        env = ", ".join(f"{m}={n}" for m, n in counter.envelope.items())
        console.print(
            f"[dim]message-envelope tokens subtracted: {env} "
            f"(use --raw-claude for request-level counts)[/dim]"
        )
    console.print(
        "[dim]local/tiktoken rows are priced at the ground-truth model's "
        "input rate — that number is the size of the estimation error, "
        "not a quote.[/dim]"
    )

    # ---- token boundary visualization
    if args.viz != "none":
        for r in reports:
            if args.viz_file and r.path.name != args.viz_file:
                continue
            snippet = r.text[: args.viz_chars] if args.viz_chars else r.text
            if args.viz in ("tiktoken", "both"):
                viz_tiktoken(snippet, enc, f"{r.path.name} · tiktoken/{args.tiktoken_encoding}")
            if args.viz in ("local", "both") and tok is not None:
                viz_local(snippet, tok, f"{r.path.name} · {args.local_model}")

    # ---- real calls, logged append-only
    if args.call:
        console.print(f"\n[bold]Making {len(reports)} billed call(s) on {args.call_model}[/bold]")
        for r in reports:
            usage = make_call(client, args.call_model, r.text, args.call_max_tokens)
            record = {
                "ts": utc_now(),
                "run_id": run_id,
                "day": 1,
                "phase": 0,
                "component": "drill",
                "provider": "anthropic",
                "model": args.call_model,
                **usage,
                "cost_usd": round(
                    pricing.cost_usd(
                        args.call_model,
                        input_tokens=usage["input_tokens"],
                        output_tokens=usage["output_tokens"],
                        cache_creation_input_tokens=usage["cache_creation_input_tokens"],
                        cache_read_input_tokens=usage["cache_read_input_tokens"],
                        on=today,
                    ),
                    8,
                ),
                "tags": {"drill": "day-001-tokens", "sample": r.path.name},
            }
            append_cost(record, args.costs_log)
            console.print(
                f"  {r.path.name:<18} in={record['input_tokens']:>5} "
                f"out={record['output_tokens']:>4} ttft={record['ttft_ms']}ms "
                f"latency={record['latency_ms']}ms ${record['cost_usd']:.6f}"
            )
        console.print(f"[dim]appended to {args.costs_log}[/dim]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""plot — fit the prefill and decode slopes from runs.jsonl, and draw them.

Reads the runs phases.py wrote (the latest session by default), drops warm-ups, and reports:

    TTFT   = a + b x prompt_tokens      b is the prefill cost per token
    decode = c + d x output_tokens      d is the decode cost per token (TPOT)

plus the checks the lesson asks for: TTFT must not depend on output length, decode gets a
little slower as the prompt grows (the KV cache, measured), and the decode rate against the
memory-bandwidth ceiling.

Usage (from the repo root):
    uv run python drills/day-002-inference/plot.py
    uv run python drills/day-002-inference/plot.py --bandwidth 273   # GB/s, if not detected
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.table import Table

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DAY1 = REPO_ROOT / "drills" / "day-001-tokens"
if str(DAY1) not in sys.path:
    sys.path.insert(0, str(DAY1))

import pricing  # noqa: E402  (Day 1: one place for Claude prices)

DEFAULT_RUNS = HERE / "runs.jsonl"
DEFAULT_PLOTS = HERE / "plots"
PRICE_MODEL = "claude-opus-5"

# Unified-memory bandwidth (GB/s) for Apple chips that ship in one configuration only.
# Max chips come in two bandwidths, so for those (and anything else) pass --bandwidth.
APPLE_BANDWIDTH_GBS = {
    "Apple M1": 68.25,
    "Apple M1 Pro": 200,
    "Apple M2": 100,
    "Apple M2 Pro": 200,
    "Apple M3": 100,
    "Apple M3 Pro": 150,
    "Apple M4": 120,
    "Apple M4 Pro": 273,
}

console = Console()


# ------------------------------------------------------------------ data


def load(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(
            f"No runs at {path}. Run phases.py first: "
            "uv run python drills/day-002-inference/phases.py"
        )
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def select(rows: list[dict], session: str = "latest") -> list[dict]:
    """Rows of one session (run ids sort by time, so the max is the newest), or all."""
    if session == "all":
        return rows
    if session == "latest":
        session = max(r["session"] for r in rows)
    picked = [r for r in rows if r["session"] == session]
    if not picked:
        raise SystemExit(f"No runs with session {session!r} in this file.")
    return picked


def measured(rows: list[dict]) -> list[dict]:
    return [r for r in rows if not r["warmup"]]


def median_by(rows: list[dict], keys: tuple[str, ...], value: str) -> dict:
    groups: dict[tuple, list[float]] = defaultdict(list)
    for r in rows:
        if r.get(value) is not None:
            groups[tuple(r[k] for k in keys)].append(r[value])
    return {k[0] if len(k) == 1 else k: statistics.median(v) for k, v in groups.items()}


# ------------------------------------------------------------------ fits


@dataclass(frozen=True)
class Fit:
    intercept: float
    slope: float
    r2: float

    def at(self, x: float) -> float:
        return self.intercept + self.slope * x


def fit_line(xs, ys) -> Fit:
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    ss_res = float(np.sum((y - (intercept + slope * x)) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return Fit(float(intercept), float(slope), 1 - ss_res / ss_tot if ss_tot else 1.0)


def summarise(rows: list[dict], bandwidth_gbs: float | None = None) -> dict:
    """Every number the notes ask for, from one session's measured (non-warm-up) rows."""
    m = measured(rows)
    if not m:
        raise SystemExit("Only warm-up runs in this session; nothing to fit.")
    prompts = sorted({r["prompt_tokens_requested"] for r in m})
    outputs = sorted({r["output_tokens_requested"] for r in m})
    p_lo, p_hi, o_lo, o_hi = prompts[0], prompts[-1], outputs[0], outputs[-1]

    ttft = fit_line([r["prompt_tokens_actual"] for r in m], [r["ttft_ms"] for r in m])
    decode = fit_line([r["output_tokens_actual"] for r in m], [r["decode_ms"] for r in m])

    # §4: fit the shorter prompts only, and see where the longest one lands against that line.
    lower = [r for r in m if r["prompt_tokens_requested"] < p_hi]
    top_vs_lower = None
    if len({r["prompt_tokens_requested"] for r in lower}) >= 2:
        lower_fit = fit_line(
            [r["prompt_tokens_actual"] for r in lower], [r["ttft_ms"] for r in lower]
        )
        top = [r for r in m if r["prompt_tokens_requested"] == p_hi]
        top_ttft = statistics.median(r["ttft_ms"] for r in top)
        top_p = statistics.median(r["prompt_tokens_actual"] for r in top)
        top_vs_lower = {
            "fit": lower_fit,
            "predicted_ms": lower_fit.at(top_p),
            "measured_ms": top_ttft,
        }

    # Independence check: per prompt length, how far apart are the TTFTs of different outputs?
    ttft_cells = median_by(m, ("prompt_tokens_requested", "output_tokens_requested"), "ttft_ms")
    spread = {}
    for p in prompts:
        vals = [ttft_cells[(p, o)] for o in outputs if (p, o) in ttft_cells]
        spread[p] = (max(vals) - min(vals)) / statistics.median(vals) * 100 if vals else None

    # The KV cache, measured: engine TPOT by prompt length, on runs long enough to be stable.
    long_out = [r for r in m if r["output_tokens_requested"] >= min(100, o_hi)]
    tpot = median_by(long_out, ("prompt_tokens_requested",), "tpot_ms")
    kv = None
    if p_lo in tpot and p_hi in tpot and p_hi > p_lo:
        per_tok = (tpot[p_hi] - tpot[p_lo]) / (p_hi - p_lo)
        kv = {
            "tpot_lo": tpot[p_lo],
            "tpot_hi": tpot[p_hi],
            "pct": (tpot[p_hi] / tpot[p_lo] - 1) * 100,
            "doubles_at": p_lo + tpot[p_lo] / per_tok if per_tok > 0 else None,
        }

    # Prediction: decode can't beat bandwidth / model size.
    model_bytes = next((r.get("model_bytes") for r in m if r.get("model_bytes")), None)
    chip = next((r.get("machine", {}).get("chip") for r in m), None)
    bw = bandwidth_gbs or APPLE_BANDWIDTH_GBS.get(chip or "")
    decode_measured = median_by(long_out, ("prompt_tokens_requested",), "decode_tok_per_s")
    ceiling = None
    if bw and model_bytes:
        cap = bw * 1e9 / model_bytes
        ceiling = {
            "bandwidth_gbs": bw,
            "model_gb": model_bytes / 1e9,
            "tok_s": cap,
            "measured_tok_s": decode_measured.get(p_lo),
            "pct": decode_measured.get(p_lo, 0) / cap * 100,
        }

    def workload(p: int, o: int) -> dict | None:
        cell = [
            r for r in m if r["prompt_tokens_requested"] == p and r["output_tokens_requested"] == o
        ]
        if not cell:
            return None
        pin = round(statistics.median(r["prompt_tokens_actual"] for r in cell))
        out = round(statistics.median(r["output_tokens_actual"] for r in cell))
        return {
            "prompt": pin,
            "output": out,
            "ttft_ms": statistics.median(r["ttft_ms"] for r in cell),
            "total_ms": statistics.median(r["total_ms"] for r in cell),
            "usd": pricing.cost_usd(PRICE_MODEL, input_tokens=pin, output_tokens=out),
        }

    return {
        "model": m[0]["model"],
        "machine": m[0].get("machine", {}),
        "session": m[0]["session"],
        "runs": len(m),
        "warmups": len(rows) - len(m),
        "prompts": prompts,
        "outputs": outputs,
        "ttft_fit": ttft,
        "decode_fit": decode,
        "prefill_tok_s": 1000 / ttft.slope,
        "decode_tok_s": 1000 / decode.slope,
        "ratio": decode.slope / ttft.slope,
        "overhead_ms": statistics.median(r["overhead_ms"] for r in m),
        "top_vs_lower": top_vs_lower,
        "ttft_spread_pct": spread,
        "prefill_rate": median_by(m, ("prompt_tokens_requested",), "prefill_tok_per_s"),
        "tpot_by_prompt": tpot,
        "kv": kv,
        "ceiling": ceiling,
        "truncated": [
            r["tags"]["cell"]
            for r in m
            if r["prompt_tokens_actual"] != r["prompt_tokens_requested"]
        ],
        "workload_a": workload(p_hi, o_lo),
        "workload_b": workload(p_lo, o_hi),
    }


# ------------------------------------------------------------------ plots


def draw(rows: list[dict], s: dict, out_dir: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    m = measured(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    colors = ["#2f6fdf", "#e0a100", "#d6453d", "#2e9e6a", "#7a52c7"]
    title_tail = f"{s['model']} · {s['machine'].get('chip', '')}"
    paths = []

    # 1. TTFT against prompt length, one series per output length.
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    for i, o in enumerate(s["outputs"]):
        pts = [r for r in m if r["output_tokens_requested"] == o]
        ax.scatter(
            [r["prompt_tokens_actual"] for r in pts],
            [r["ttft_ms"] / 1000 for r in pts],
            s=28,
            alpha=0.75,
            color=colors[i % 5],
            label=f"{o} output tokens",
        )
    f = s["ttft_fit"]
    xs = np.linspace(0, max(s["prompts"]) * 1.03, 100)
    ax.plot(
        xs,
        f.at(xs) / 1000,
        color="#333",
        lw=1.5,
        label=f"fit: {ms(f.intercept)} ms + {f.slope * 1000:,.0f} ms per 1k tokens (R² {f.r2:.4f})",
    )
    if s["top_vs_lower"]:
        lf = s["top_vs_lower"]["fit"]
        ax.plot(
            xs,
            lf.at(xs) / 1000,
            color="#999",
            lw=1.2,
            ls="--",
            label=f"prompts < {s['prompts'][-1]:,} only: {ms(lf.intercept)} ms + "
            f"{lf.slope * 1000:,.0f} ms per 1k tokens (R² {lf.r2:.4f})",
        )
    ax.set_xlabel("prompt tokens")
    ax.set_ylabel("time to first token (s)")
    headline = f"≈ {s['prefill_tok_s']:,.0f} tokens/s"
    if s["top_vs_lower"]:
        tv = s["top_vs_lower"]
        gap = (tv["measured_ms"] / tv["predicted_ms"] - 1) * 100
        headline = (
            f"≈ {1000 / tv['fit'].slope:,.0f} tokens/s, and the longest prompt "
            f"{gap:+.0f}% above that line"
        )
    ax.set_title(f"Prefill: {headline}\n{title_tail}", fontsize=11)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8.5, loc="upper left")
    p = out_dir / "ttft-vs-prompt.png"
    fig.tight_layout()
    fig.savefig(p)
    plt.close(fig)
    paths.append(p)

    # 2. Decode time against output length, one series per prompt length.
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    for i, pr in enumerate(s["prompts"]):
        pts = [r for r in m if r["prompt_tokens_requested"] == pr]
        ax.scatter(
            [r["output_tokens_actual"] for r in pts],
            [r["decode_ms"] / 1000 for r in pts],
            s=28,
            alpha=0.75,
            color=colors[i % 5],
            label=f"{pr:,}-token prompt",
        )
        if len({r["output_tokens_actual"] for r in pts}) >= 2:
            pf = fit_line([r["output_tokens_actual"] for r in pts], [r["decode_ms"] for r in pts])
            xs = np.linspace(0, max(s["outputs"]) * 1.03, 100)
            ax.plot(
                xs,
                pf.at(xs) / 1000,
                color=colors[i % 5],
                lw=1,
                ls="--",
                alpha=0.8,
                label=f"  {pr:,}: {pf.slope:.1f} ms per token ({1000 / pf.slope:.1f} tok/s)",
            )
    f = s["decode_fit"]
    xs = np.linspace(0, max(s["outputs"]) * 1.03, 100)
    ax.plot(
        xs,
        f.at(xs) / 1000,
        color="#333",
        lw=1.5,
        label=f"all prompts: {ms(f.intercept)} ms + {f.slope:.1f} ms per token (R² {f.r2:.4f})",
    )
    ax.set_xlabel("output tokens (measured eval_count)")
    ax.set_ylabel("decode time = total − TTFT (s)")
    ax.set_title(
        f"Decode: ≈ {s['decode_tok_s']:.1f} tokens/s, slower as the prompt grows (KV cache)"
        f"\n{title_tail}",
        fontsize=11,
    )
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8.5, loc="upper left")
    p = out_dir / "decode-vs-output.png"
    fig.tight_layout()
    fig.savefig(p)
    plt.close(fig)
    paths.append(p)
    return paths


# ------------------------------------------------------------------ report


def ms(x: float) -> str:
    """Whole milliseconds, without the "-0" a tiny negative intercept would print."""
    return f"{round(x) or 0:,}"


def report(s: dict) -> None:
    mc = s["machine"]
    console.print(
        f"[bold]{s['model']}[/bold] on {mc.get('chip')} · Ollama {mc.get('ollama')} · "
        f"session {s['session']} · {s['runs']} runs (+{s['warmups']} warm-ups dropped)\n"
    )

    t = Table(title="1. The two slopes")
    for col in ("", "fit", "per token", "throughput", "R²"):
        t.add_column(col, justify="right" if col else "left")
    tf, df = s["ttft_fit"], s["decode_fit"]
    t.add_row(
        "prefill (TTFT vs prompt)",
        f"{ms(tf.intercept)} ms + {tf.slope * 1000:,.0f} ms/1k",
        f"{tf.slope:.2f} ms",
        f"{s['prefill_tok_s']:,.0f} tok/s",
        f"{tf.r2:.4f}",
    )
    if s["top_vs_lower"]:
        lf = s["top_vs_lower"]["fit"]
        t.add_row(
            f"  prefill, prompts < {s['prompts'][-1]:,} only",
            f"{ms(lf.intercept)} ms + {lf.slope * 1000:,.0f} ms/1k",
            f"{lf.slope:.2f} ms",
            f"{1000 / lf.slope:,.0f} tok/s",
            f"{lf.r2:.4f}",
        )
    t.add_row(
        "decode (time vs output)",
        f"{ms(df.intercept)} ms + {df.slope:.1f} ms/tok",
        f"{df.slope:.2f} ms",
        f"{s['decode_tok_s']:,.1f} tok/s",
        f"{df.r2:.4f}",
    )
    console.print(t)
    console.print(
        f"Per token, prefill is [bold]{s['ratio']:.1f}x[/bold] faster than decode. "
        f"Fixed overhead before prefill (TTFT − engine prefill, median): "
        f"[bold]{s['overhead_ms']:.0f} ms[/bold]; the fitted intercept is {ms(tf.intercept)} ms."
    )
    if s["top_vs_lower"]:
        tv = s["top_vs_lower"]
        gap = (tv["measured_ms"] / tv["predicted_ms"] - 1) * 100
        console.print(
            f"Longest prompt: {tv['measured_ms'] / 1000:.1f} s measured vs "
            f"{tv['predicted_ms'] / 1000:.1f} s on the line through the shorter prompts "
            f"([bold]{gap:+.1f}%[/bold]). Above the line is attention's quadratic term (§4)."
        )
        if tf.intercept < 0:
            console.print(
                "[dim]A negative intercept on the full fit is that curve pulling the line: use "
                "the shorter-prompt fit for the per-token cost, and the measured overhead "
                "for the fixed cost.[/dim]"
            )

    t = Table(title="Reading speed by prompt length (engine)")
    t.add_column("prompt", justify="right")
    t.add_column("prefill tok/s", justify="right")
    t.add_column("TTFT spread across outputs", justify="right")
    t.add_column("decode TPOT", justify="right")
    for p in s["prompts"]:
        sp = s["ttft_spread_pct"].get(p)
        tp = s["tpot_by_prompt"].get(p)
        t.add_row(
            f"{p:,}",
            f"{s['prefill_rate'].get(p, 0):,.0f}",
            f"{sp:.1f}%" if sp is not None else "—",
            f"{tp:.2f} ms ({1000 / tp:.1f} tok/s)" if tp else "—",
        )
    console.print(t)
    console.print(
        "[dim]TTFT spread should be a few percent at most: the first token can't depend on how "
        "many come after it.[/dim]"
    )

    if s["ceiling"]:
        c = s["ceiling"]
        console.print(
            f"\n2. Ceiling: {c['bandwidth_gbs']:g} GB/s ÷ {c['model_gb']:.2f} GB = "
            f"[bold]{c['tok_s']:.1f} tok/s[/bold]. Measured at the shortest prompt: "
            f"{c['measured_tok_s']:.1f} tok/s = [bold]{c['pct']:.0f}%[/bold] of the ceiling."
        )
    else:
        console.print(
            "\n2. Ceiling: unknown chip bandwidth. Look yours up and pass --bandwidth <GB/s>."
        )

    t = Table(title=f"3. The two workloads (API cost at {PRICE_MODEL} rates)")
    for col in ("", "prompt", "output", "TTFT", "total", "local $", "API $"):
        t.add_column(col, justify="right" if col else "left")
    for name, w in (
        ("A: long prompt, short answer", s["workload_a"]),
        ("B: short prompt, long answer", s["workload_b"]),
    ):
        if w:
            t.add_row(
                name,
                f"{w['prompt']:,}",
                f"{w['output']:,}",
                f"{w['ttft_ms'] / 1000:.2f} s",
                f"{w['total_ms'] / 1000:.2f} s",
                "$0",
                f"${w['usd']:.4f}",
            )
    console.print(t)
    console.print(
        "[dim]Token counts are the local model's; the API column prices them at Claude rates "
        f"(pricing.py, verified {pricing.LAST_VERIFIED}) to show the shape, not a quote.[/dim]"
    )

    if s["kv"]:
        k = s["kv"]
        dbl = f"{k['doubles_at']:,.0f}" if k["doubles_at"] else "never (no growth)"
        console.print(
            f"\n4. KV cache: TPOT {k['tpot_lo']:.2f} ms at {s['prompts'][0]:,} tokens vs "
            f"{k['tpot_hi']:.2f} ms at {s['prompts'][-1]:,} → [bold]{k['pct']:+.1f}%[/bold]. "
            f"On a straight line, TPOT doubles at about [bold]{dbl}[/bold] prompt tokens."
        )
    if s["truncated"]:
        console.print(
            f"\n[yellow]Prompt length differs from the request in {len(s['truncated'])} runs "
            f"({', '.join(sorted(set(s['truncated'])))}). Check num_ctx.[/yellow]"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--runs", type=Path, default=DEFAULT_RUNS, help="JSONL from phases.py")
    ap.add_argument("--session", default="latest", help="session id, 'latest' or 'all'")
    ap.add_argument("--bandwidth", type=float, help="memory bandwidth in GB/s, for the ceiling")
    ap.add_argument("--plots", type=Path, default=DEFAULT_PLOTS, help="where to write PNGs")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = select(load(args.runs), args.session)
    s = summarise(rows, args.bandwidth)
    report(s)
    for p in draw(rows, s, args.plots):
        shown = p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p
        console.print(f"[dim]wrote {shown}[/dim]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

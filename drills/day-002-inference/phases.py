#!/usr/bin/env python3
"""phases — time the two jobs inside every request: prefill (reading) and decode (writing).

Runs a matrix of prompt lengths x output lengths against a local Ollama model, streams each
response so time-to-first-token (TTFT) is measured by the clock, and records Ollama's own
engine timings next to it. One JSON line per run goes to runs.jsonl; plot.py fits the slopes.

Usage (from the repo root, with Ollama running):
    uv run python drills/day-002-inference/phases.py            # full matrix, ~30 min
    uv run python drills/day-002-inference/phases.py --quick    # smoke test, ~1 min
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import secrets
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import httpx
from rich.console import Console
from rich.table import Table

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DAY1 = REPO_ROOT / "drills" / "day-001-tokens"
if str(DAY1) not in sys.path:
    sys.path.insert(0, str(DAY1))

import tokviz  # noqa: E402  (Day 1: Ollama tag -> HF tokenizer, run ids, timestamps)

DRILL = "day-002-inference"
DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_PROMPTS = [100, 1000, 4000, 16000]
DEFAULT_OUTPUTS = [10, 100, 500]
DEFAULT_REPEATS = 5
DEFAULT_NUM_CTX = 24576
DEFAULT_FILLER = DAY1 / "samples" / "logline.txt"
DEFAULT_OUT = HERE / "runs.jsonl"
QUICK = {"prompts": [100, 1000], "outputs": [10, 100], "repeats": 2}

# Asking for something that does not want to stop, so the model writes the tokens we ask
# for instead of emitting EOS early. Rates are still divided by the *measured* eval_count.
INSTRUCTION = (
    "The log above is filler for a timing test. Ignore it. List the integers from 1 to 1000, "
    "one per line, with no other text."
)

console = Console()


class Tokenizer(Protocol):
    """The three HF tokenizer methods this drill uses. Tests pass a fake."""

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]: ...
    def decode(self, ids: list[int]) -> str: ...
    def apply_chat_template(self, messages, tokenize: bool, add_generation_prompt: bool): ...


# ------------------------------------------------------------------ prompts


def count_tokens(tok: Tokenizer, text: str) -> int:
    return len(tok.encode(text, add_special_tokens=False))


def filler_ids(tok: Tokenizer, text: str, at_least: int) -> list[int]:
    """Token ids of `text`, repeated until there are at least `at_least` of them."""
    one = count_tokens(tok, text)
    reps = max(1, math.ceil(at_least / max(one, 1)) + 1)
    return tok.encode(text * reps, add_special_tokens=False)


def render(tok: Tokenizer, nonce: str, body: str) -> str:
    """The exact text the engine reads. The nonce sits at the start of the context, so
    no earlier run's KV cache matches more than the first few template tokens."""
    messages = [
        {"role": "system", "content": f"Session {nonce}. You are a helpful assistant."},
        {"role": "user", "content": f"{body}\n\n{INSTRUCTION}"},
    ]
    return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


def build_prompt(tok: Tokenizer, target: int, filler: list[int], nonce: str) -> tuple[str, int]:
    """A prompt of exactly `target` tokens (as the engine counts them), or the closest
    length reachable when token merges at the cut make the exact one impossible."""
    overhead = count_tokens(tok, render(tok, nonce, ""))
    if target < overhead:
        raise ValueError(f"{target} tokens is shorter than the prompt scaffolding ({overhead})")

    k = min(target - overhead, len(filler))
    best: tuple[int, str, int] | None = None
    for _ in range(40):
        text = render(tok, nonce, tok.decode(filler[:k]))
        n = count_tokens(tok, text)
        if best is None or abs(n - target) < best[0]:
            best = (abs(n - target), text, n)
        if n == target:
            break
        k = max(0, min(len(filler), k + (target - n)))
    assert best is not None
    return best[1], best[2]


# ------------------------------------------------------------------ one run


def stream_once(
    client: httpx.Client,
    model: str,
    prompt: str,
    num_predict: int,
    num_ctx: int,
    clock: Callable[[], float] = time.perf_counter,
) -> dict:
    """POST one raw prompt, stream the reply, return wall-clock and engine timings."""
    payload = {
        "model": model,
        "prompt": prompt,
        "raw": True,  # the prompt already carries the chat template
        "stream": True,
        "keep_alive": "15m",
        "options": {
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "temperature": 0,
            "seed": 42,
        },
    }
    t0 = clock()
    ttft = None
    final: dict = {}
    with client.stream("POST", "/api/generate", json=payload) as resp:
        if resp.status_code != 200:
            resp.read()
            raise RuntimeError(f"Ollama returned {resp.status_code}: {resp.text.strip()}")
        for line in resp.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            if "error" in chunk:
                raise RuntimeError(f"Ollama error: {chunk['error']}")
            if ttft is None and chunk.get("response"):
                ttft = clock() - t0
            if chunk.get("done"):
                final = chunk
    total = clock() - t0
    if ttft is None:  # nothing was generated; the first token is the end
        ttft = total
    return {"ttft_s": ttft, "total_s": total, "engine": final}


def make_record(
    raw: dict,
    *,
    session: str,
    model: str,
    model_bytes: int | None,
    num_ctx: int,
    prompt_requested: int,
    prompt_built: int,
    output_requested: int,
    repeat: int,
    warmup: bool,
    machine: dict,
) -> dict:
    ns = 1e-6  # engine durations are nanoseconds; records are milliseconds
    e = raw["engine"]
    prompt_actual = e.get("prompt_eval_count", 0)
    cached = e.get("prompt_eval_cached_count", 0)
    out_actual = e.get("eval_count", 0)
    prefill_ms = e.get("prompt_eval_duration", 0) * ns
    decode_ms_engine = e.get("eval_duration", 0) * ns
    ttft_ms = raw["ttft_s"] * 1000
    total_ms = raw["total_s"] * 1000
    read = prompt_actual - cached
    return {
        "ts": tokviz.utc_now(),
        "run_id": tokviz.ulid(),
        "session": session,
        "day": 2,
        "phase": 0,
        "component": "drill",
        "provider": "ollama",
        "model": model,
        "model_bytes": model_bytes,
        "num_ctx": num_ctx,
        "prompt_tokens_requested": prompt_requested,
        "prompt_tokens_built": prompt_built,
        "prompt_tokens_actual": prompt_actual,
        "prompt_tokens_cached": cached,
        "output_tokens_requested": output_requested,
        "output_tokens_actual": out_actual,
        "repeat": repeat,
        "warmup": warmup,
        "ttft_ms": round(ttft_ms, 1),
        "total_ms": round(total_ms, 1),
        "decode_ms": round(total_ms - ttft_ms, 1),
        "prefill_ms_engine": round(prefill_ms, 1),
        "decode_ms_engine": round(decode_ms_engine, 1),
        "load_ms_engine": round(e.get("load_duration", 0) * ns, 1),
        "overhead_ms": round(ttft_ms - prefill_ms, 1),
        "tpot_ms": round(decode_ms_engine / out_actual, 2) if out_actual else None,
        "prefill_tok_per_s": round(read / (prefill_ms / 1000), 1) if prefill_ms else None,
        "decode_tok_per_s": round(out_actual / (decode_ms_engine / 1000), 1)
        if decode_ms_engine
        else None,
        "done_reason": e.get("done_reason"),
        "machine": machine,
        "tags": {"drill": DRILL, "cell": f"p{prompt_requested}-o{output_requested}"},
    }


# ------------------------------------------------------------------ environment


def machine_info(client: httpx.Client) -> dict:
    chip = platform.processor() or platform.machine()
    mem = None
    if sys.platform == "darwin":
        try:
            chip = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
            ).stdout.strip()
            mem = int(
                subprocess.run(
                    ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True
                ).stdout.strip()
            )
        except OSError, ValueError:
            pass
    try:
        engine = client.get("/api/version").json().get("version")
    except httpx.HTTPError:
        engine = None
    return {"chip": chip, "memory_bytes": mem, "os": platform.platform(), "ollama": engine}


def model_size(client: httpx.Client, model: str) -> int | None:
    for m in client.get("/api/tags").json().get("models", []):
        if m.get("name") == model or m.get("model") == model:
            return m.get("size")
    return None


def check_ollama(client: httpx.Client, model: str) -> int | None:
    try:
        client.get("/api/version").raise_for_status()
    except httpx.HTTPError:
        console.print(
            f"[red]Can't reach Ollama at {client.base_url}.[/red] Open the Ollama app, or run "
            "`ollama serve` in another terminal, then try again."
        )
        raise SystemExit(2) from None
    size = model_size(client, model)
    if size is None:
        console.print(f"[red]Model {model!r} isn't installed.[/red] Run: ollama pull {model}")
        raise SystemExit(2)
    return size


# ------------------------------------------------------------------ main


def median_table(rows: list[dict], key: str, title: str, prompts, outputs) -> Table:
    t = Table(title=title)
    t.add_column("prompt \\ output", justify="right")
    for o in outputs:
        t.add_column(f"{o}", justify="right")
    for p in prompts:
        cells = []
        for o in outputs:
            vals = [
                r[key]
                for r in rows
                if r["prompt_tokens_requested"] == p
                and r["output_tokens_requested"] == o
                and not r["warmup"]
            ]
            cells.append(f"{statistics.median(vals):,.0f} ms" if vals else "—")
        t.add_row(f"{p:,}", *cells)
    return t


def parse_list(s: str) -> list[int]:
    return [int(x) for x in s.split(",") if x.strip()]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model", default=DEFAULT_MODEL, help="Ollama tag (default: %(default)s)")
    ap.add_argument(
        "--prompts",
        type=parse_list,
        default=DEFAULT_PROMPTS,
        help="prompt lengths in tokens, comma-separated (default: 100,1000,4000,16000)",
    )
    ap.add_argument(
        "--outputs",
        type=parse_list,
        default=DEFAULT_OUTPUTS,
        help="output lengths in tokens, comma-separated (default: 10,100,500)",
    )
    ap.add_argument(
        "--repeats",
        type=int,
        default=DEFAULT_REPEATS,
        help="runs per cell; the first is a warm-up (default: %(default)s)",
    )
    ap.add_argument(
        "--num-ctx",
        type=int,
        default=DEFAULT_NUM_CTX,
        help="context window, set on every request (default: %(default)s)",
    )
    ap.add_argument(
        "--filler",
        type=Path,
        default=DEFAULT_FILLER,
        help="text the prompts are cut from (default: Day 1 logline.txt)",
    )
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="JSONL file to append to")
    ap.add_argument("--host", default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    ap.add_argument(
        "--quick",
        action="store_true",
        help="smoke test: prompts 100,1000 x outputs 10,100 x 2 repeats",
    )
    args = ap.parse_args(argv)
    if args.quick:
        args.prompts, args.outputs, args.repeats = (
            QUICK["prompts"],
            QUICK["outputs"],
            QUICK["repeats"],
        )
    if args.repeats < 2:
        ap.error("--repeats must be at least 2: the first run of every cell is a warm-up")
    need = max(args.prompts) + max(args.outputs)
    if args.num_ctx < need:
        ap.error(f"--num-ctx {args.num_ctx} is too small: the largest cell needs {need}")
    if not args.host.startswith("http"):
        args.host = f"http://{args.host}"
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    client = httpx.Client(base_url=args.host, timeout=httpx.Timeout(600.0, connect=5.0))
    model_bytes = check_ollama(client, args.model)
    machine = machine_info(client)

    tok = tokviz.local_tokenizer(args.model)
    if tok is None:
        console.print(
            "[red]Prompts are built to an exact token count, so the tokenizer is required.[/red]"
        )
        return 2
    filler = filler_ids(tok, args.filler.read_text(encoding="utf-8"), max(args.prompts))

    session = tokviz.ulid()
    cells = [(p, o) for p in sorted(args.prompts) for o in sorted(args.outputs)]
    n_runs = len(cells) * args.repeats
    console.print(
        f"[bold]{args.model}[/bold] on {machine['chip']} · Ollama {machine['ollama']} · "
        f"num_ctx {args.num_ctx:,} · {len(cells)} cells x {args.repeats} = {n_runs} runs\n"
        f"session {session} → {args.out.relative_to(REPO_ROOT) if args.out.is_relative_to(REPO_ROOT) else args.out}"  # noqa: E501
    )

    # Load the model off the clock, so no cell pays for it.
    t = time.perf_counter()
    stream_once(client, args.model, "hi", 1, args.num_ctx)
    console.print(f"[dim]model loaded in {time.perf_counter() - t:.1f} s[/dim]")

    rows: list[dict] = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    i = 0
    with args.out.open("a", encoding="utf-8") as f:
        for p, o in cells:
            for rep in range(args.repeats):
                i += 1
                prompt, built = build_prompt(tok, p, filler, secrets.token_hex(4))
                raw = stream_once(client, args.model, prompt, o, args.num_ctx)
                rec = make_record(
                    raw,
                    session=session,
                    model=args.model,
                    model_bytes=model_bytes,
                    num_ctx=args.num_ctx,
                    prompt_requested=p,
                    prompt_built=built,
                    output_requested=o,
                    repeat=rep,
                    warmup=rep == 0,
                    machine=machine,
                )
                f.write(json.dumps(rec) + "\n")
                f.flush()
                rows.append(rec)

                flags = []
                if rec["prompt_tokens_actual"] != p:
                    flags.append(f"[yellow]prompt {rec['prompt_tokens_actual']:,}≠{p:,}[/yellow]")
                if rec["prompt_tokens_cached"] > 16:
                    flags.append(f"[yellow]{rec['prompt_tokens_cached']} cached[/yellow]")
                if rec["output_tokens_actual"] < o:
                    flags.append(f"[yellow]stopped at {rec['output_tokens_actual']}[/yellow]")
                console.print(
                    f"[dim]{i:>3}/{n_runs}[/dim] p{p:>6,} o{o:>4} "
                    f"{'warm-up' if rep == 0 else f'rep {rep}':>7}  "
                    f"TTFT {rec['ttft_ms']:>7,.0f} ms  total {rec['total_ms']:>7,.0f} ms  "
                    f"read {rec['prefill_tok_per_s'] or 0:>4,.0f}/s  "
                    f"write {rec['decode_tok_per_s'] or 0:>4.1f}/s " + " ".join(flags)
                )

    prompts, outputs = sorted(args.prompts), sorted(args.outputs)
    console.print()
    console.print(median_table(rows, "ttft_ms", "Median time to first token", prompts, outputs))
    console.print(median_table(rows, "total_ms", "Median total latency", prompts, outputs))
    console.print(f"\nNext: uv run python drills/{DRILL}/plot.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

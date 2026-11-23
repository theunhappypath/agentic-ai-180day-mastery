#!/usr/bin/env python3
"""demo — the Day 5 run: twelve calls through the lab, then the report.

  1. Unload the model, so the first call pays the real cold start.
  2. Ten everyday questions with the settings from lab.toml.
  3. Day 4's town directory (7,884 tokens) with a 4,096-token window: the lab should flag it.
  4. The same document with a 16,384-token window: no warning, the right answer.

Usage (from the repo root, with Ollama running; about 2 minutes):
    uv run python drills/day-005-lab/demo.py                    # writes runs.jsonl here
    uv run lab report --log drills/day-005-lab/runs.jsonl       # read it back any time
"""

from __future__ import annotations

import argparse
from pathlib import Path

import httpx

from agentic_mastery.lab import call, load_config
from agentic_mastery.lab.cli import DOC_PROMPT
from agentic_mastery.lab.cli import main as lab_cli

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
TOWN = REPO_ROOT / "drills" / "day-004-context" / "samples" / "town-8k.txt"
LOCKER_Q = "What is Wilhelmina Fairbanks's locker code? Reply with the number only."

QUESTIONS = [
    "What is 17 times 23? Reply with the number only.",
    "Translate 'good morning' into French.",
    "In one sentence, what does a load balancer do?",
    "List three ways to make a slow web page faster, one line each.",
    "Write a haiku about debugging.",
    "Summarise in one sentence: the meeting moved to Thursday because the client is "
    "travelling on Wednesday.",
    "Is 'recieve' spelled correctly? Answer yes or no, then give the correct spelling.",
    "Give a one-line Python expression that reverses a string s.",
    "What is the capital of Australia? One word.",
    "Explain what an API is to a ten-year-old, in two sentences.",
]


def unload(url: str, model: str) -> None:
    """Ask Ollama to drop the model from memory, so the next call starts cold."""
    httpx.post(f"{url}/api/generate", json={"model": model, "keep_alive": 0}, timeout=60)


def show(step: str, res) -> None:
    r = res.record
    flags = " ".join(f"[{w['code']}]" for w in res.warnings)
    answer = " ".join(res.text.split())[:60]
    print(
        f"{step:<10} read {r['tokens_read']:>6,}  ttft {r['ttft_ms']:>6,} ms  "
        f"total {r['latency_ms']:>6,} ms  load {r.get('load_ms', 0):>6,} ms  {answer} {flags}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=HERE / "runs.jsonl")
    args = ap.parse_args()
    args.out = args.out.resolve()

    config = load_config(REPO_ROOT / "lab.toml")
    model = config.defaults.model
    print(f"{model} · log: {args.out.relative_to(REPO_ROOT)}\n")
    unload(config.ollama_url, model)

    common = {"config": config, "log_path": args.out, "day": 5}
    for i, q in enumerate(QUESTIONS, 1):
        res = call(q, tags={"drill": "day-005-lab", "step": f"q{i:02d}"}, **common)
        show(f"q{i:02d}", res)

    doc = DOC_PROMPT.format(doc=TOWN.read_text(encoding="utf-8"), question=LOCKER_Q)
    for ctx in (4096, 16384):
        res = call(doc, num_ctx=ctx, tags={"drill": "day-005-lab", "step": f"town-{ctx}"}, **common)
        show(f"town-{ctx}", res)

    print()
    lab_cli(["--config", str(config.path), "report", "--log", str(args.out)])


if __name__ == "__main__":
    main()

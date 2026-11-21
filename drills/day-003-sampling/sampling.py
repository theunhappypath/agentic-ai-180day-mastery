"""Day 3: same question, different answer.

Asks a local Ollama model the same questions many times, at different temperatures, with and
without a seed, and counts how many different answers come back. Also reads the model's odds
for the first few tokens. Everything is written to one JSON file.

    uv run python drills/day-003-sampling/sampling.py            # full run, a few minutes
    uv run python drills/day-003-sampling/sampling.py --quick    # 3 runs per setting, ~20 s

My run from the video is in results-m4-pro.json next to this file.
"""

import argparse
import concurrent.futures as cf
import json
import math
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
URL = "http://localhost:11434/api/generate"

COFFEE = "Suggest one name for a new coffee shop. Reply with the name only."
CAPITAL = "What is the capital of Australia? Reply with the city name only."
STORY = "Write a two-sentence story about a robot who learns to bake bread."

COFFEE_TEMPS = (0, 0.7, 1.0, 1.5)
CAPITAL_TEMPS = (0, 1.0, 1.5)
STORY_SEED_RUNS = 5  # story with and without a seed: 5 runs each


def generate(model, prompt, temperature, seed=None, num_predict=80, logprobs=False):
    options = {"temperature": temperature, "num_predict": num_predict}
    if seed is not None:
        options["seed"] = seed
    body = {"model": model, "prompt": prompt, "stream": False, "options": options}
    if logprobs:
        body |= {"logprobs": True, "top_logprobs": 10}
    req = urllib.request.Request(
        URL, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def summary(outputs):
    """How many different answers, and how often each one came back (most common first)."""
    counts = {}
    for o in outputs:
        counts[o] = counts.get(o, 0) + 1
    return {"distinct": len(counts), "counts": dict(sorted(counts.items(), key=lambda kv: -kv[1]))}


def odds(response, steps=4):
    """The model's top 10 choices, with probabilities, at each of the first few tokens."""
    return {
        "response": response["response"],
        "steps": [
            {
                "chosen": step["token"],
                "top": [
                    (t["token"], round(math.exp(t["logprob"]), 4)) for t in step["top_logprobs"]
                ],
            }
            for step in response["logprobs"][:steps]
        ],
    }


def check_ollama(model):
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
            names = {m["name"] for m in json.load(r)["models"]}
    except urllib.error.URLError, OSError:
        sys.exit("Can't reach Ollama. Open the Ollama app, or run `ollama serve`.")
    if model not in names:
        sys.exit(f"Model {model} isn't installed. Run: ollama pull {model}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default="qwen2.5:7b-instruct")
    ap.add_argument("--runs", type=int, default=20, help="runs per setting (default 20)")
    ap.add_argument("--quick", action="store_true", help="3 runs per setting")
    ap.add_argument("--out", type=Path, default=HERE / "results.json")
    args = ap.parse_args()
    n = 3 if args.quick else args.runs
    model = args.model
    check_ollama(model)

    def ask(prompt, temperature, seed=None, num_predict=80):
        return generate(model, prompt, temperature, seed, num_predict)["response"].strip()

    def runs(prompt, temperature, runs=n, seed=None, num_predict=80):
        print(
            f"  {runs} x temperature {temperature}" + (f", seed {seed}" if seed is not None else "")
        )
        return [ask(prompt, temperature, seed, num_predict) for _ in range(runs)]

    results = {"model": model, "runs_per_setting": n, "date": time.strftime("%Y-%m-%d")}

    print("Reading the odds")
    results["odds_coffee"] = odds(generate(model, COFFEE, 0, num_predict=8, logprobs=True))
    results["odds_capital"] = odds(generate(model, CAPITAL, 0, num_predict=8, logprobs=True))

    print("Coffee shop name")
    results["coffee_by_temperature"] = {
        str(t): summary(runs(COFFEE, t, num_predict=12)) for t in COFFEE_TEMPS
    }
    print("Capital of Australia")
    results["capital_by_temperature"] = {
        str(t): summary(runs(CAPITAL, t, num_predict=8)) for t in CAPITAL_TEMPS
    }

    print("Robot story")
    story_n = min(STORY_SEED_RUNS, n)
    results["story_temp0_sequential"] = summary(runs(STORY, 0))
    results["story_temp1_seed42"] = summary(runs(STORY, 1.0, runs=story_n, seed=42))
    results["story_temp1_noseed"] = summary(runs(STORY, 1.0, runs=story_n))

    # Temperature 0 again, but all requests at once, so they can share batches on the server.
    print(f"  {n} x temperature 0, sent at once")
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        outs = list(pool.map(lambda _: ask(STORY, 0), range(n)))
    results["story_temp0_concurrent"] = summary(outs)

    args.out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print_report(results)
    print(f"\nSaved to {args.out}")


def print_report(results):
    print("\nDifferent answers out of", results["runs_per_setting"])
    for t, s in results["coffee_by_temperature"].items():
        print(f"  coffee   temperature {t:<4} {s['distinct']}")
    for t, s in results["capital_by_temperature"].items():
        print(f"  capital  temperature {t:<4} {s['distinct']}")
    for key, label in [
        ("story_temp0_sequential", "temperature 0, one after another"),
        ("story_temp0_concurrent", "temperature 0, sent at once"),
        ("story_temp1_noseed", "temperature 1, no seed"),
        ("story_temp1_seed42", "temperature 1, seed 42"),
    ]:
        s = results[key]
        print(f"  story    {label:<33} {s['distinct']} of {sum(s['counts'].values())}")


if __name__ == "__main__":
    main()

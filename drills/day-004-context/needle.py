"""Day 4: one fact hidden in a long document.

Builds a long made-up town directory, hides facts in it at chosen positions, and asks a local
Ollama model to find them. Four tests, all written to one JSON file:

1. one_fact        one locker code, 4 document lengths x 11 positions
2. default_window  the same kind of document sent with Ollama's default settings
3. ten_facts       ten pie ingredients spread through the document: which ones come back?
4. in_pieces       the longest ten-fact documents again, asked in 4 smaller pieces

    uv run python drills/day-004-context/needle.py            # full run, about 50 minutes
    uv run python drills/day-004-context/needle.py --quick    # small version, about 2 minutes

My run from the video is in results-m4-pro.json next to this file.
"""

import argparse
import json
import platform
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLLAMA = "http://localhost:11434"

# The haystack: short notes about made-up people. Half of them are locker codes, so the
# locker code we hide has look-alikes all around it.
# fmt: off
FIRST = ["Aarav", "Maya", "Liam", "Sofia", "Noah", "Priya", "Ethan", "Zara", "Lucas", "Ananya",
         "Omar", "Chloe", "Kenji", "Leila", "Mateo", "Ines", "Ravi", "Hana", "Felix", "Amara",
         "Diego", "Yuki", "Tariq", "Nora", "Elena", "Samir", "Ivy", "Jonas", "Mira", "Theo"]
LAST = ["Shah", "Lopez", "Chen", "Novak", "Okafor", "Iyer", "Brennan", "Sato", "Haddad", "Moreau",
        "Kaur", "Petrov", "Silva", "Nakamura", "Rossi", "Mensah", "Varga", "Jensen", "Ortiz", "Kim",
        "Fischer", "Dube", "Laine", "Costa", "Rahman", "Weber", "Quinn", "Abe", "Romero", "Lund"]
TOWNS = ["Pinecrest", "Ashford", "Millbrook", "Riverton", "Elmstead", "Harlow", "Brookvale",
         "Fernhill", "Stonebridge", "Westmere"]
# fmt: on
HOBBIES = [
    "paints old bicycles",
    "grows chillies on the balcony",
    "collects train tickets",
    "runs every Sunday",
    "plays the cello",
    "bakes sourdough",
    "repairs radios",
    "writes crossword puzzles",
    "keeps bees",
    "teaches chess at the library",
]
PETS = [
    "a grey cat",
    "two goldfish",
    "an old beagle",
    "a parrot named Pip",
    "a tortoise",
    "no pets",
    "three hens",
    "a rescue greyhound",
]

# Test 1: one fact. The name appears nowhere else in the document.
LOCKER_FACT = "Wilhelmina Fairbanks's locker code is 7342."
LOCKER_QUESTION = "What is Wilhelmina Fairbanks's locker code? Reply with the number only."
LOCKER_ANSWER = "7342"

# Test 3: ten facts, one per tenth of the document.
INGREDIENTS = [
    "cinnamon",
    "figs",
    "honey",
    "black pepper",
    "orange peel",
    "walnuts",
    "cardamom",
    "dates",
    "sea salt",
    "vanilla",
]
PIE_FACT = "One of the secret ingredients in Grandma Rosa's famous pie is {}."
PIE_QUESTION = (
    "List every secret ingredient in Grandma Rosa's famous pie mentioned in the document, "
    "separated by commas. Reply with the list only."
)
SLOTS = [(i + 0.5) / 10 for i in range(10)]  # 5%, 15%, ... 95% of the way through

TOKENS_PER_LINE = 13.6  # measured with qwen2.5's tokenizer; good enough to aim at a length
NUM_CTX = 32768  # the context window we ask Ollama for (qwen2.5:7b's limit)


def note(rng):
    """One line of the town directory."""
    who = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    if rng.random() < 0.5:
        return f"{who}'s locker code is {rng.randint(1000, 9999)}."
    town = rng.choice(TOWNS)
    return rng.choice(
        [
            f"{who} lives in {town} and {rng.choice(HOBBIES)}.",
            f"{who} moved to {town} last spring with {rng.choice(PETS)}.",
            f"On weekends, {who} {rng.choice(HOBBIES)}.",
            f"{who} works at the {town} post office and has {rng.choice(PETS)}.",
        ]
    )


def haystack(tokens, seed):
    """Roughly `tokens` tokens of directory notes, always the same for the same seed."""
    rng = random.Random(seed)
    return [note(rng) for _ in range(round(tokens / TOKENS_PER_LINE))]


def hide(lines, facts):
    """Insert each (depth, sentence) pair, depth 0.0 = first line, 1.0 = after the last line."""
    out = list(lines)
    for depth, sentence in sorted(facts, reverse=True):  # back to front keeps positions valid
        out.insert(round(depth * len(lines)), sentence)
    return out


def build_prompt(lines, question, part=False):
    what = "part of a document" if part else "a document"
    doc = " ".join(lines)
    return f"Here is {what}.\n\n<document>\n{doc}\n</document>\n\n{question}"


def found(answer, expected):
    return expected.lower() in answer.lower()


def listed(answer, items):
    """Which of `items` the answer mentions, in the order of `items`."""
    text = answer.lower()
    return [item.lower() in text for item in items]


def extras(answer, items):
    """Things the answer lists that aren't real ingredients (made up, or picked up elsewhere)."""
    real = [i.lower() for i in items]
    out = []
    for part in answer.replace("\n", ",").split(","):
        part = part.strip(" .-*").lower()
        if part and not any(r in part for r in real):
            out.append(part)
    return out


def pie_document(tokens, trial):
    """The ten-fact document for one trial. Each trial shuffles which ingredient sits where."""
    order = INGREDIENTS[:]
    random.Random(trial).shuffle(order)
    lines = hide(
        haystack(tokens, seed=100 + trial), zip(SLOTS, map(PIE_FACT.format, order), strict=True)
    )
    return lines, order  # order[i] is the ingredient at SLOTS[i]


def split(lines, pieces):
    size = -(-len(lines) // pieces)  # ceiling division
    return [lines[i : i + size] for i in range(0, len(lines), size)]


# --- talking to Ollama -------------------------------------------------------------------


def call(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(OLLAMA + path, data, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)


def generate(model, prompt, num_ctx=NUM_CTX, num_predict=80):
    options = {"temperature": 0, "num_predict": num_predict}
    if num_ctx:
        options["num_ctx"] = num_ctx  # None = Ollama's default window
    t = time.time()
    r = call(
        "/api/generate", {"model": model, "prompt": prompt, "stream": False, "options": options}
    )
    return {
        "answer": r["response"].strip(),
        "prompt_tokens": r.get("prompt_eval_count"),  # tokens the model actually read
        "seconds": round(time.time() - t, 1),
    }


def check_ollama(model):
    try:
        names = {m["name"] for m in call("/api/tags")["models"]}
    except urllib.error.URLError, OSError:
        sys.exit("Can't reach Ollama. Open the Ollama app, or run `ollama serve`.")
    if model not in names:
        sys.exit(f"Model {model} isn't installed. Run: ollama pull {model}")


def loaded_window(model):
    """The context window Ollama loaded the model with, as reported by /api/ps."""
    for m in call("/api/ps").get("models", []):
        if m["name"] == model:
            return m.get("context_length")
    return None


# --- the four tests ----------------------------------------------------------------------


def test_one_fact(model, lengths, depths):
    rows = []
    for tokens in lengths:
        lines = haystack(tokens, seed=tokens)
        for depth in depths:
            r = generate(model, build_prompt(hide(lines, [(depth, LOCKER_FACT)]), LOCKER_QUESTION))
            r |= {"length": tokens, "depth": depth, "found": found(r["answer"], LOCKER_ANSWER)}
            print(f"  {tokens:>6} tokens, fact at {depth:4.0%}: {r['answer'][:50]!r}", flush=True)
            rows.append(r)
    return rows


def test_default_window(model, tokens, depths):
    lines = haystack(tokens, seed=tokens)
    rows = []
    for depth in depths:
        prompt = build_prompt(hide(lines, [(depth, LOCKER_FACT)]), LOCKER_QUESTION)
        r = generate(model, prompt, num_ctx=None)
        r |= {"length": tokens, "depth": depth, "found": found(r["answer"], LOCKER_ANSWER)}
        print(
            f"  default settings, fact at {depth:4.0%}: read {r['prompt_tokens']} tokens,"
            f" {r['answer'][:50]!r}",
            flush=True,
        )
        rows.append(r)
    return {"window": loaded_window(model), "runs": rows}


def test_ten_facts(model, lengths, trials):
    out = {}
    for tokens in lengths:
        runs = []
        for trial in range(trials):
            lines, order = pie_document(tokens, trial)
            r = generate(model, build_prompt(lines, PIE_QUESTION))
            r |= {
                "order": order,
                "hits": listed(r["answer"], order),
                "extras": extras(r["answer"], INGREDIENTS),
            }
            print(f"  {tokens:>6} tokens, trial {trial}: {bar(r['hits'])}", flush=True)
            runs.append(r)
        out[str(tokens)] = {"by_slot": recall_by_slot(runs), "runs": runs}
    return out


def test_in_pieces(model, tokens, trials, pieces=4):
    runs = []
    for trial in range(trials):
        lines, order = pie_document(tokens, trial)
        parts = []
        for chunk in split(lines, pieces):
            parts.append(generate(model, build_prompt(chunk, PIE_QUESTION, part=True)))
        answer = ", ".join(p["answer"] for p in parts)
        r = {
            "order": order,
            "answers": [p["answer"] for p in parts],
            "prompt_tokens": [p["prompt_tokens"] for p in parts],
            "seconds": round(sum(p["seconds"] for p in parts), 1),
            "hits": listed(answer, order),
            "extras": extras(answer, INGREDIENTS),
        }
        print(f"  {tokens:>6} tokens in {pieces} pieces, trial {trial}: {bar(r['hits'])}")
        runs.append(r)
    return {"pieces": pieces, "length": tokens, "by_slot": recall_by_slot(runs), "runs": runs}


def write_sample(path=HERE / "samples" / "town-8k.txt"):
    """The 8,000-token directory with the locker code on the first line, for the `ask` command."""
    path.parent.mkdir(exist_ok=True)
    path.write_text(" ".join(hide(haystack(8000, seed=8000), [(0.0, LOCKER_FACT)])) + "\n")
    print(f"Wrote {path}")


def recall_by_slot(runs):
    """How many trials found the fact at each of the ten positions."""
    return [sum(r["hits"][i] for r in runs) for i in range(len(SLOTS))]


def bar(hits):
    return "".join("#" if h else "." for h in hits) + f"  {sum(hits)}/10"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default="qwen2.5:7b-instruct")
    ap.add_argument("--quick", action="store_true", help="short documents, about 2 minutes")
    ap.add_argument("--trials", type=int, default=5, help="ten-fact trials per length")
    ap.add_argument("--out", type=Path, default=HERE / "results.json")
    ap.add_argument("--sample", action="store_true", help="only write samples/town-8k.txt")
    ap.add_argument("--report", type=Path, help="print the summary of a saved results file")
    args = ap.parse_args()
    if args.sample:
        return write_sample()
    if args.report:
        return print_report(json.loads(args.report.read_text(encoding="utf-8")))
    model = args.model
    check_ollama(model)

    if args.quick:
        lengths, depths, pie_lengths, trials = (2000, 8000), (0.0, 0.5, 1.0), (8000,), 1
    else:
        lengths, depths = (2000, 8000, 16000, 30000), [d / 10 for d in range(11)]
        pie_lengths, trials = (4000, 8000, 16000, 30000), args.trials

    results = {
        "model": model,
        "date": time.strftime("%Y-%m-%d"),
        "ollama": call("/api/version")["version"],
        "machine": platform.platform(),
        "num_ctx": NUM_CTX,
    }

    def save():
        args.out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    print("Test 2: default settings (run first, while the default window is loaded)")
    results["default_window"] = test_default_window(model, 8000, (0.0, 0.5, 1.0))
    save()
    print("Test 1: one locker code")
    results["one_fact"] = test_one_fact(model, lengths, depths)
    save()
    print("Test 3: ten pie ingredients")
    results["ten_facts"] = test_ten_facts(model, pie_lengths, trials)
    save()
    print("Test 4: the longest document, asked in pieces")
    results["in_pieces"] = test_in_pieces(model, pie_lengths[-1], trials)
    save()

    print_report(results)
    print(f"\nSaved to {args.out}")


def print_report(results):
    d = results["default_window"]
    print(f"\nDefault settings (window {d['window']} tokens):")
    for r in d["runs"]:
        print(f"  fact at {r['depth']:4.0%}: read {r['prompt_tokens']} tokens, found={r['found']}")

    print("\nOne fact, found at each position (0% = start, 100% = end):")
    rows = results["one_fact"]
    for tokens in sorted({r["length"] for r in rows}):
        mine = [r for r in rows if r["length"] == tokens]
        marks = "".join("#" if r["found"] else "." for r in mine)
        print(f"  {tokens:>6} tokens  {marks}  {sum(r['found'] for r in mine)}/{len(mine)}")

    print("\nTen facts: how often the fact at each position came back")
    print(" " * 17 + "start" + " " * 31 + "end")
    rows = [(f"{int(k):>6} tokens", t) for k, t in results["ten_facts"].items()]
    p = results["in_pieces"]
    rows.append((f"{p['length']:>6} in {p['pieces']}  ", p))
    for label, t in rows:
        n, cells = len(t["runs"]), "   ".join(str(c) for c in t["by_slot"])
        got = sum(t["by_slot"])
        print(f"  {label}  {cells}   {got}/{n * 10} ({got / (n * 10):.0%}), {n} trials")


if __name__ == "__main__":
    main()

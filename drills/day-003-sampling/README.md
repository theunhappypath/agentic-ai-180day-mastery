# Day 3: Same question, different answer

The code from the Day 3 video. A model doesn't pick one next word. It writes a list of odds
and then spins a wheel to pick from it. This drill asks a local model the same questions
many times and counts how many different answers come back: at different temperatures, with
and without a seed, and with requests sent one after another or all at once.

Roadmap: [Phase 0, Day 3](../../docs/phase-00-foundations.md) · my run:
[`results-m4-pro.json`](results-m4-pro.json)

## What's in this folder

| File | What it does |
|---|---|
| `sampling.py` | Reads the model's odds for the first few tokens, then asks three questions many times each and writes every answer, with counts, to `results.json`. |
| `results-m4-pro.json` | My run from the video (Apple M4 Pro, `qwen2.5:7b-instruct`, 20 Nov 2026). |
| `test_sampling.py` | Offline tests. No Ollama needed. |

The three questions:

- **Coffee:** "Suggest one name for a new coffee shop. Reply with the name only." Lots of good answers.
- **Capital:** "What is the capital of Australia? Reply with the city name only." One right answer.
- **Story:** "Write a two-sentence story about a robot who learns to bake bread." Long answer, so small differences add up.

## The 30-second version (from the video)

Install [Ollama](https://ollama.com) and `jq` (`brew install jq` on a Mac), download the model,
then paste this into your terminal as one line. It defines a tiny command called `ask`:

```bash
ask() { curl -s localhost:11434/api/generate -d "{\"model\":\"qwen2.5:7b-instruct\",\"prompt\":\"Suggest one name for a new coffee shop. Reply with the name only.\",\"stream\":false,\"options\":{\"temperature\":$1${2:+,\"seed\":$2}}}" | jq -r .response; }
```

The first number is the temperature. Turn it up and watch the names wander:

```bash
ask 0; ask 1; ask 2; ask 3; ask 4; ask 5
```

Add a second number to set the seed. Same seed, same answer, even at temperature 1:

```bash
ask 1 42; ask 1 42; ask 1 42
```

On my laptop that prints "Caffeine Dreams" three times.

## Run it on your machine

You need about 6 GB of free memory and a few minutes. No API key: everything runs locally.

**1. Install uv and Ollama.** uv manages Python for you. Ollama runs the model.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install Ollama from [ollama.com/download](https://ollama.com/download) and open it.

**2. Download the model** (4.7 GB, once):

```bash
ollama pull qwen2.5:7b-instruct
```

**3. Download the code** (the `day-003` branch is the version shown in the video):

```bash
git clone -b day-003 https://github.com/theunhappypath/agentic-ai-180day-mastery.git
cd agentic-ai-180day-mastery
```

**4. Install the dependencies and check everything works** (offline, about a second):

```bash
uv sync
```

```bash
uv run pytest
```

**5. Smoke test** (about 20 seconds, 3 runs per setting):

```bash
uv run python drills/day-003-sampling/sampling.py --quick --out /tmp/quick.json
```

**6. The full run** (20 runs per setting, a few minutes):

```bash
uv run python drills/day-003-sampling/sampling.py
```

It prints how many different answers each setting gave and saves everything to
`drills/day-003-sampling/results.json`.

## What you should see

My run: Apple M4 Pro, `qwen2.5:7b-instruct`, Ollama 0.40.16 with its default trimming
(top-k 40, top-p 0.9), 20 runs per setting unless noted.

**The odds for the first token.** The model is unsure about the coffee shop and certain
about the capital:

| Question | Top choices for the first token |
|---|---|
| Coffee | "B" (→ Brew…) 70% · "C" 10% · "M" 6.5% · "Java" 5.8% · "Bean" 3.1% · "Morning" 1.4% |
| Capital | "Can" 99.65%, then "berra" ≈ 100% |

**Different answers out of 20:**

| Temperature | Coffee | Capital |
|---|---:|---:|
| 0 | 1 ("Brew Haven", 20 times) | 1 |
| 0.7 | 5 | |
| 1.0 | 9 | 1 |
| 1.5 | 10 | 1 |

**The robot story:**

| Setting | Runs | Different stories |
|---|---:|---:|
| Temperature 1, no seed | 5 | 5 (one switched into Chinese halfway through a sentence) |
| Temperature 1, seed 42 | 5 | 1 |
| Temperature 0, one after another | 20 | 1 |
| Temperature 0, 20 requests at once | 20 | 1 |

What these numbers mean:

- **Randomness only shows where the model is unsure.** The coffee question spreads out as
  the temperature rises. The capital never moves, even at 1.5, because "Can" already has
  99.65% of the wheel.
- **A seed makes a random answer repeatable.** Same seed, same spins, same story.
- **Temperature 0 was fully repeatable on one laptop**, even with 20 requests at once. That
  is not a guarantee everywhere. Cloud servers group many users' requests into batches, and
  the grouping changes the order of the maths. Computers round, so order matters:

  ```bash
  python3 -c "print((0.1 + 0.2) + 0.3, 0.1 + (0.2 + 0.3))"
  ```

  prints `0.6000000000000001 0.6`. When two tokens are nearly tied, a difference that small
  can flip which one wins. Anthropic's API documentation says results are not fully
  deterministic even at temperature 0.

Your names will differ from mine above temperature 0: that's the point. The capital and the
temperature-0 rows should match.

## Options

| Option | What it does |
|---|---|
| `--quick` | 3 runs per setting. About 20 seconds. |
| `--runs 50` | Runs per setting (default 20). The seeded and unseeded stories always use at most 5. |
| `--model llama3.1:8b` | Use another Ollama model. |
| `--out file.json` | Where to write the results. |

## If something goes wrong

| You see | Fix |
|---|---|
| `Can't reach Ollama` | Open the Ollama app, or run `ollama serve` in another terminal. |
| `Model ... isn't installed` | `ollama pull qwen2.5:7b-instruct` |
| `ask` prints `null` | The model name or JSON is off. Re-paste the `ask` line exactly as one line. |
| `jq: command not found` | `brew install jq`, or drop `\| jq -r .response` to see the raw reply. |

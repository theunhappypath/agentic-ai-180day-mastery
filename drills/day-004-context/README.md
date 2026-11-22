# Day 4: One fact hidden in a long document

The code from the Day 4 video. You can paste a long document into a model, but does it
actually read all of it? This drill builds a long made-up town directory, hides facts in it
at chosen positions, and asks a local model to find them: one fact, then ten, at document
lengths from 2,000 to 30,000 tokens.

Roadmap: [Phase 0, Day 4](../../docs/phase-00-foundations.md) · my run:
[`results-m4-pro.json`](results-m4-pro.json)

## What's in this folder

| File | What it does |
|---|---|
| `needle.py` | Builds the documents, runs the four tests below against Ollama, and writes every answer to `results.json`. |
| `samples/town-8k.txt` | An 8,000-token directory with the locker code on the very first line. Used by the `ask` command. |
| `results-m4-pro.json` | My run from the video (Apple M4 Pro, `qwen2.5:7b-instruct`). |
| `test_needle.py` | Offline tests. No Ollama needed. |

The document is thousands of short notes about made-up people: where they live, their
hobbies, their pets, and, in half the notes, their locker code. The facts we hide:

- **One fact:** "Wilhelmina Fairbanks's locker code is 7342." It sits among about 280 other
  locker codes per 8,000 tokens, but her name appears nowhere else.
- **Ten facts:** "One of the secret ingredients in Grandma Rosa's famous pie is cinnamon."
  Ten of these, one in each tenth of the document, then we ask for the whole list.

## The four tests

| Test | What it asks | Why |
|---|---|---|
| `default_window` | The locker code, 8,000-token document, Ollama's default settings | Shows what Ollama does with a document bigger than its default window. |
| `one_fact` | The locker code, 4 lengths × 11 positions (0%, 10% … 100%) | The classic "needle in a haystack" test. |
| `ten_facts` | All ten ingredients, 4 lengths × 5 trials | A harder, more realistic task. Which positions get forgotten? |
| `in_pieces` | All ten ingredients from the 30,000-token documents, asked in 4 pieces | One fix, measured. |

Every request uses temperature 0 (Day 3) and asks Ollama for a 32,768-token window, the
most `qwen2.5:7b-instruct` supports, except `default_window`, which uses no setting at all.

## The 30-second version (from the video)

Install [Ollama](https://ollama.com) and `jq` (`brew install jq` on a Mac), download the model,
download this repo (step 3 below), then paste this into your terminal as one line. It defines
a tiny command called `ask` that sends the sample document and the question:

```bash
ask() { jq -n --rawfile doc drills/day-004-context/samples/town-8k.txt --arg q "What is Wilhelmina Fairbanks's locker code? Reply with the number only." --argjson ctx "${1:-0}" '{model:"qwen2.5:7b-instruct",prompt:"Here is a document.\n\n<document>\n\($doc)</document>\n\n\($q)",stream:false,options:({temperature:0}+(if $ctx>0 then {num_ctx:$ctx} else {} end))}' | curl -s localhost:11434/api/generate -d @- | jq -r '"read \(.prompt_eval_count) tokens: \(.response)"'; }
```

With no number, Ollama uses its default window:

```bash
ask
```

With a number, you choose the window size in tokens:

```bash
ask 16384
```

On my laptop:

```text
read 2050 tokens: There is no information about a person named Wilhelmina Fairbanks in the given text, so I cannot provide a locker code for her.
read 7913 tokens: 7342
```

The document is 7,913 tokens. With its default settings, Ollama kept only the last 2,050 and
dropped the rest, the first line included. No error, no warning. The model answered honestly
about the part it was given.

## Run it on your machine

You need about 8 GB of free memory. No API key: everything runs locally.

**1. Install uv and Ollama.** uv manages Python for you. Ollama runs the model.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install Ollama from [ollama.com/download](https://ollama.com/download) and open it.

**2. Download the model** (4.7 GB, once):

```bash
ollama pull qwen2.5:7b-instruct
```

**3. Download the code** (the `day-004` branch is the version shown in the video):

```bash
git clone -b day-004 https://github.com/theunhappypath/agentic-ai-180day-mastery.git
cd agentic-ai-180day-mastery
```

**4. Install the dependencies and check everything works** (offline, a few seconds):

```bash
uv sync
```

```bash
uv run pytest
```

**5. Smoke test** (about 2 minutes, short documents only):

```bash
uv run python drills/day-004-context/needle.py --quick --out /tmp/quick.json
```

**6. The full run** (about 50 minutes on my laptop; most of it is the 30,000-token documents):

```bash
uv run python drills/day-004-context/needle.py
```

It prints a summary and saves every answer to `drills/day-004-context/results.json`.

To see my run's summary without running anything:

```bash
uv run python drills/day-004-context/needle.py --report drills/day-004-context/results-m4-pro.json
```

## What you should see

My run: Apple M4 Pro, `qwen2.5:7b-instruct`, Ollama 0.40.17, temperature 0, 22 Nov 2026.

**Default settings.** Ollama loaded the model with a 4,096-token window and read only the
last 2,050 tokens of the 7,913-token document:

| Locker code at | Tokens read | Answer |
|---|---:|---|
| the start | 2,050 | "There is no information about a person named Wilhelmina Fairbanks…" |
| the middle | 2,050 | the same |
| the end | 2,050 | 7342 |

**One fact.** Found at every position, at every length: 44 out of 44.

| Document | Tokens read | Found (11 positions) |
|---|---:|---:|
| 2,000 | 2,025 | 11 / 11 |
| 8,000 | 7,913 | 11 / 11 |
| 16,000 | 15,711 | 11 / 11 |
| 30,000 | 29,481 | 11 / 11 |

**Ten facts.** How many of the 5 trials recalled the fact at each position:

| Document | 5% | 15% | 25% | 35% | 45% | 55% | 65% | 75% | 85% | 95% | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4,000 | 5 | 5 | 5 | 4 | 5 | 5 | 5 | 4 | 5 | 4 | 47 / 50 (94%) |
| 8,000 | 5 | 5 | 5 | 5 | 5 | 3 | 4 | 4 | 3 | 3 | 42 / 50 (84%) |
| 16,000 | 5 | 4 | 4 | 1 | 2 | 3 | 4 | 3 | 4 | 5 | 35 / 50 (70%) |
| 30,000 | 5 | 1 | 5 | 3 | 4 | 1 | 2 | 2 | 4 | 5 | 32 / 50 (64%) |
| **30,000 in 4 pieces** | 5 | 5 | 5 | 5 | 5 | 5 | 3 | 5 | 5 | 5 | **48 / 50 (96%)** |

Reading the 30,000-token document took about 126 seconds per question. The four pieces of
about 7,400 tokens each took about 91 seconds in total.

What these numbers mean:

- **Check what the model actually read.** A document bigger than the window doesn't cause an
  error in Ollama. It gets cut, from the front. `prompt_eval_count` in the reply tells you how
  many tokens the model read. Other tools and APIs handle this differently: some refuse the
  request, some cut it. Find out which yours does.
- **Finding one fact is not the same as reading the whole document.** The classic
  needle-in-a-haystack test passed everywhere. Asking for all ten facts did not.
- **The middle is where facts go missing.** At 16,000 and 30,000 tokens, the first and last
  facts came back in every trial. The eight in between came back 25 and 22 times out of 40.
  This U shape has a name, "lost in the middle", from a 2023 paper by Liu and colleagues.
- **The model doesn't tell you what it missed.** Every short list was presented as the
  complete answer. Once, at 16,000 tokens, it added "sourdough", a hobby from the directory,
  as an ingredient.
- **Smaller pieces helped, and were faster.** The same 30,000-token documents, asked in four
  pieces, gave 48 of 50 instead of 32 of 50.

This is one model, one machine and one made-up document. Your exact numbers will differ.
Run it on your model before trusting a long-context feature with something important.

## Your challenge

Run the ten-fact test on a different model, for example `--model llama3.1:8b`, which accepts
much longer documents. Does it lose the middle too? At what length does it drop below 9 out
of 10? Post your table in the video's comments.

## Options

| Option | What it does |
|---|---|
| `--quick` | 2,000 and 8,000 tokens only, 3 positions, 1 trial. About 2 minutes. |
| `--trials 10` | Ten-fact trials per length (default 5). |
| `--model llama3.1:8b` | Use another Ollama model. |
| `--out file.json` | Where to write the results. |
| `--sample` | Only rewrite `samples/town-8k.txt`. |

The lengths are aimed with a fixed 13.6 tokens per note, measured with qwen2.5's tokenizer.
Other models split text differently (Day 1), so check `prompt_tokens` in the results.
`qwen2.5:7b-instruct` stops at 32,768 tokens, so the longest test is 30,000. For a model with a
bigger window, raise `NUM_CTX` and add lengths in `main()`.

## If something goes wrong

| You see | Fix |
|---|---|
| `Can't reach Ollama` | Open the Ollama app, or run `ollama serve` in another terminal. |
| `Model ... isn't installed` | `ollama pull qwen2.5:7b-instruct` |
| `ask` prints `jq: error: Could not open ...town-8k.txt` | Run it from the repo folder (`cd agentic-ai-180day-mastery`). |
| `ask` prints `read null tokens: null` | Ollama isn't running, or the `ask` line got split. Re-paste it as one line. |
| `ask` prints a different token count | Your Ollama picks its default window from your machine's memory. The point stands if the count is smaller than the document. |
| The full run is very slow | Reading 30,000 tokens takes a couple of minutes per question on a laptop (Day 2). Use `--quick`, or stop after the first tests: results are saved after each one. |

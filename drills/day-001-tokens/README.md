# Day 1: Tokens, the real unit of LLM cost

The code from the Day 1 video. `tokviz` takes text files and shows, side by side, how many
characters, bytes and **tokens** each one is, and what that costs on Claude.

Lesson: [docs/days/day-001-tokenization.md](../../docs/days/day-001-tokenization.md) ·
my results: [notes/day-001.md](../../notes/day-001.md)

## What's in this folder

| File | What it does |
|---|---|
| `tokviz.py` | The tool. Counts tokens three ways and prints the tables. |
| `pricing.py` | Claude prices in one place, with the date they were last checked. |
| `samples/` | Five test files: English prose, log lines, JSON, Python, Marathi. |
| `test_tokviz.py` | Offline tests. No API key needed. |

It counts tokens three ways:

- **Claude `count_tokens`**: the real count from Anthropic. It's free, but it needs an API key.
- **Local Qwen tokenizer**: runs on your machine. It's the only one that shows where each token starts and ends.
- **tiktoken**: OpenAI's tokenizer. Many people use it to estimate Claude tokens, and this tool shows how far off that estimate is.

## Run it on your machine

You need a terminal and an Anthropic API key from
[console.anthropic.com](https://console.anthropic.com/). Counting tokens is free.

**1. Install uv** (it manages Python for you, so no separate Python install is needed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Download the code** (the `day-001` branch is the version shown in the video):

```bash
git clone -b day-001 https://github.com/theunhappypath/agentic-ai-180day-mastery.git
cd agentic-ai-180day-mastery
```

**3. Install the dependencies:**

```bash
uv sync
```

**4. Add your API key.** Copy the example file, then open `.env` and paste your key after
`ANTHROPIC_API_KEY=`. `.env` is git-ignored, so the key never gets committed.

```bash
cp .env.example .env
```

**5. Check everything works** (offline, takes about a second):

```bash
uv run pytest
```

**6. Run the tool on the five samples:**

```bash
uv run python drills/day-001-tokens/tokviz.py drills/day-001-tokens/samples/*
```

The first run downloads the Qwen tokenizer (about 11 MB) and tiktoken's vocabulary. After
that it takes a few seconds.

**7. See where the tokens break**, coloured, on the log line:

```bash
uv run python drills/day-001-tokens/tokviz.py drills/day-001-tokens/samples/logline.txt --viz tiktoken --viz-chars 200
```

Swap `--viz tiktoken` for `--viz local` to see the Qwen tokens. Red pieces are characters that
were split across two tokens. On `devanagari.txt` you'll see a lot of them.

## What you should see

Look at the last table, **"The four numbers"**, and its `chars/tok` column. Higher means
cheaper text. Your numbers should match these:

| file | chars/tok (Claude) | tiktoken error |
|---|---:|---:|
| prose.txt | 3.35 | -25.7% |
| sample.py | 2.61 | -37.4% |
| payload.json | 2.25 | -26.8% |
| logline.txt | 1.63 | -23.8% |
| devanagari.txt | 1.33 | -48.3% |

What these numbers mean:

- Log lines cost about **twice as much as prose** for the same amount of text.
- tiktoken **undercounts every file**, by 24% to 48%. Don't use it to estimate a Claude bill.

## Try it on your own text

Pass any text files:

```bash
uv run python drills/day-001-tokens/tokviz.py path/to/your/file.txt
```

Useful options:

| Option | What it does |
|---|---|
| `--models claude-opus-5,claude-haiku-4-5` | Compare two Claude models. The first one is the ground truth. |
| `--viz both --viz-file prose.txt` | Show token boundaries for one file only. |
| `--raw-claude` | Don't subtract the ~6 tokens of message wrapping that every request adds. |
| `--call` | Make one real (billed) call per file and log it to `costs.jsonl`. This costs real money, a few cents for the samples. |

## If something goes wrong

| You see | Fix |
|---|---|
| `ANTHROPIC_API_KEY is not set` | You skipped step 4, or `.env` isn't in the repo root. |
| `uv: command not found` | Open a new terminal after installing uv. |
| `Local tokenizer ... unavailable` | No internet on the first run. The tool still runs without the Qwen rows. |
| `introductory rate expired` warning | Harmless. Prices were checked on the date shown, so check the [pricing page](https://claude.com/pricing#api) before trusting the dollar columns. |

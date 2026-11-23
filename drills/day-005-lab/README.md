# Day 5: Set up your AI lab

The code from the Day 5 video. Days 1 to 4 each measured one thing with their own script:
tokens and cost, reading and writing speed, temperature, the context window. Today those
pieces become one small lab that every experiment from here on runs through:

- **one settings file**, [`lab.toml`](../../lab.toml): model, temperature, seed, window size,
  answer length. Sent with every request, so nothing is left to a tool's hidden default.
- **one door for every model call**, `call()`: it counts the tokens it sends, times the
  call, checks the model read everything, prices it, and writes it down.
- **one notebook**, `costs.jsonl`: one line per call, never rewritten, with enough detail to
  run that exact call again.

And one command, `lab`, to check your setup, ask a question, and read the notebook back.

Roadmap: [Phase 0, Day 5](../../docs/phase-00-foundations.md) · code:
[`src/agentic_mastery/lab/`](../../src/agentic_mastery/lab/__init__.py) · my run:
[`results-m4-pro.jsonl`](results-m4-pro.jsonl)

## What's where

| File | What it does |
|---|---|
| [`lab.toml`](../../lab.toml) | The settings. Change them here, or for one call with `--num-ctx 16384` and friends. |
| `src/agentic_mastery/lab/call.py` | `call()`: settings → count → send → check → record. |
| `src/agentic_mastery/lab/providers.py` | Talks to Ollama (local) or Claude (API). Streams, so the first token is timed. |
| `src/agentic_mastery/lab/tokens.py` | Counts tokens with the model's own tokenizer (Day 1). |
| `src/agentic_mastery/lab/pricing.py` | Prices per model, with the date they were last checked (Day 1). |
| `src/agentic_mastery/lab/doctor.py` | `lab doctor`: is this machine ready? |
| `src/agentic_mastery/lab/report.py` | `lab report`: calls, tokens, speed (p50 and p95), cost, warnings. |
| `tests/test_lab.py` | 14 offline tests, including Day 4's silent cut. No Ollama needed. |
| `demo.py` | The run from the video: 12 calls, then the report. |
| `results-m4-pro.jsonl` | My run (Apple M4 Pro, `qwen2.5:7b-instruct`). |

## The five steps inside `call()`

```python
from agentic_mastery.lab import call

result = call("In one sentence, what does a load balancer do?", day=5)
print(result.text)
print(result.record["latency_ms"], result.warnings)
```

| Step | What happens | From |
|---|---|---|
| 1. Settings | Read `lab.toml`, apply this call's overrides. A typo in a setting name is an error, not a silent default. | Days 3, 4 |
| 2. Count | Count the tokens we're about to send. If they won't fit the window, warn **before** sending. | Days 1, 4 |
| 3. Send | Stream the request. Time the first token and the whole call. | Day 2 |
| 4. Check | Did the model read everything we sent? Did the answer stop at the length limit? Is there a price for this model? | Day 4 |
| 5. Record | Append one line to `costs.jsonl`. | Day 1 |

One line of the notebook (the last call of my run, shortened):

```json
{
  "ts": "2026-11-23T17:45:40.031Z",
  "run_id": "01M84R6XDZ7RMBJEZ1QFZS54BK",
  "model": "qwen2.5:7b-instruct",
  "model_digest": "845dbda0ea48",
  "settings": {"temperature": 0.0, "seed": 42, "num_ctx": 16384, "max_tokens": 512},
  "tokens_sent": 7884,
  "tokens_read": 7913,
  "output_tokens": 5,
  "ttft_ms": 27120,
  "latency_ms": 27219,
  "load_ms": 1846, "prefill_ms": 25213, "decode_ms": 104,
  "cost_usd": 0.0,
  "warnings": [],
  "git": {"commit": "4bebdf3abc02", "dirty": false},
  "machine": {"os": "Darwin 27.2.0", "chip": "Apple M4 Pro"},
  "tags": {"drill": "day-005-lab", "step": "town-16384"}
}
```

Which model file, which settings, which version of the code, which machine: enough to run it
again and compare. The prompt itself isn't stored, only a fingerprint (`prompt_sha256`), so
the log is safe to share.

`tokens_read` is a little bigger than `tokens_sent` because Ollama wraps your message in the
model's chat template (about 30 tokens) before the model reads it. When `tokens_read` is
**smaller** than `tokens_sent`, something was cut, and the lab says so.

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

**3. Download the code** (the `day-005` branch is the version shown in the video):

```bash
git clone -b day-005 https://github.com/theunhappypath/agentic-ai-180day-mastery.git
cd agentic-ai-180day-mastery
```

**4. Install and run the tests** (offline, a few seconds):

```bash
uv sync
```

```bash
uv run pytest
```

**5. Check your lab:**

```bash
uv run lab doctor
```

**6. Ask something.** The call is written to `costs.jsonl`:

```bash
uv run lab ask "In one sentence, what does a load balancer do?"
```

```bash
uv run lab last
```

**7. Replay Day 4's silent cut**, then fix it:

```bash
uv run lab ask --num-ctx 4096 --file drills/day-004-context/samples/town-8k.txt "What is Wilhelmina Fairbanks's locker code? Reply with the number only."
```

```bash
uv run lab ask --num-ctx 16384 --file drills/day-004-context/samples/town-8k.txt "What is Wilhelmina Fairbanks's locker code? Reply with the number only."
```

**8. Read the notebook back:**

```bash
uv run lab report
```

**Or the whole run from the video in one go** (about 2 minutes):

```bash
uv run python drills/day-005-lab/demo.py
```

To see my run's report without running anything:

```bash
uv run lab report --log drills/day-005-lab/results-m4-pro.jsonl
```

## What you should see

My run: Apple M4 Pro, `qwen2.5:7b-instruct` (digest `845dbda0ea48`), Ollama 0.40.17,
23 Nov 2026, code at commit `4bebdf3`.

**`lab doctor`:**

```text
 ✓ settings  lab.toml: ollama qwen2.5:7b-instruct, temperature 0, seed 42, num_ctx 8,192, max_tokens 512
 ✓ secrets   .env ignored by git · ANTHROPIC_API_KEY set
 ✓ ollama    running at http://localhost:11434 · version 0.40.17
 ✓ model     qwen2.5:7b-instruct · 4.7 GB · digest 845dbda0ea48
 ✓ window    num_ctx 8,192 of this model's maximum 32,768
 ✓ tokens    exact counts for qwen2.5:7b-instruct (its own tokenizer)
 ! prices    last checked 2026-08-26 (89 days ago)
 ✓ log       costs.jsonl · 0 calls so far
 ✓ git       commit 4bebdf3abc02 · clean

Lab ready.
```

**The Day 4 replay.** Same document (7,884 tokens), same question, two window sizes:

| Window (`num_ctx`) | Tokens read | Answer | Time | Lab warnings |
|---:|---:|---|---:|---|
| 4,096 | 2,050 | "There is no information about a person named Wilhelmina Fairbanks…" | 7.2 s | `wont_fit` before sending, `truncated` after |
| 16,384 | 7,913 | 7342 | 27.2 s | none |

On Day 4 the cut was silent. In the lab, it's two warnings and a line in the log.

**`lab report`** over all 12 calls of `demo.py`:

| Calls | Tokens read | Written | First token p50 | Total p50 | Total p95 | Cost | Warnings |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | 10,389 | 194 | 121 ms | 524 ms | 27.2 s | $0 | 2 |

What these numbers mean:

- **p50 and p95 tell different stories.** Half the calls finished in about half a second
  (p50). The slowest one in twenty (p95) took 27 seconds: the 8,000-token document, which the
  model has to read before it writes a word (Day 2). An average would hide both.
- **The first call pays for loading.** The first question took 1.1 s, 0.8 s of it loading
  the model into memory. Changing `num_ctx` reloads the model too (`load_ms` in the log).
- **Local calls cost $0 per token.** Their cost is your machine's time, which is why the
  latency columns matter. With `--provider anthropic`, the same log records dollars.
- **Prices go stale.** `lab doctor` warns when the price table is more than 30 days old.

This is one model on one machine. Your timings will differ; that's what the log is for.

## Use it from your own code

Every drill from Day 6 on calls models like this:

```python
from agentic_mastery.lab import call

res = call(prompt, day=6, tags={"drill": "day-006-budget"}, num_ctx=16384)
if res.warnings:
    print(res.warnings)
```

To try Claude instead of a local model, put `ANTHROPIC_API_KEY` in `.env` (copy
`.env.example`; `.env` is never committed) and pass `provider="anthropic",
model="claude-haiku-4-5"`. That call costs real money, a fraction of a cent for a short
question, and the log records exactly how much.

## Your challenge

Add your own guard to `check()` in `src/agentic_mastery/lab/call.py`. Two ideas:

- warn when a call takes longer than a limit you set in `lab.toml` (say 10 seconds);
- warn when the answer is empty.

Write a test for it in `tests/test_lab.py` first, using the `fake_send` helper so it runs
without a model. Post your guard in the video's comments.

## `lab` commands

| Command | What it does |
|---|---|
| `uv run lab doctor` | Checks settings, secrets, Ollama, the model, the window, the tokenizer, prices, the log and git. |
| `uv run lab ask "..."` | One call through the lab. Add `--file`, `--num-ctx`, `--model`, `--temperature`, `--max-tokens`, `--provider`, `--tag key=value`. |
| `uv run lab last` | The last line of the log, in full. |
| `uv run lab report` | Every call so far, per model. `--tag drill=day-005-lab` to filter, `--log` for another file. |

## If something goes wrong

| You see | Fix |
|---|---|
| `✗ ollama not reachable` | Open the Ollama app, or run `ollama serve` in another terminal. |
| `✗ model ... not downloaded` | `ollama pull qwen2.5:7b-instruct` |
| `! tokens no tokenizer` | The first run downloads the tokenizer (~7 MB) from Hugging Face. Without internet, counts are estimates and the truncation check only flags big gaps. |
| `✗ secrets .env is NOT ignored by git` | Add `.env` to `.gitignore` before you put a key in it. |
| `lab.toml: unknown key(s)` | A setting name has a typo. The lab refuses to guess what you meant. |
| A different `tokens read` on the 4,096 replay | The cut depends on Ollama's version. The point stands if it's smaller than `tokens sent`. |

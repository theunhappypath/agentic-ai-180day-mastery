---
day: 1
phase: 0
week: 1
title: "Tokenization and the real unit of cost"
slug: "day-001-tokenization"
mode: "learn"
duration_min: 120
concept_min: 40
practical_min: 80
capstone_version: null
deliverable: null
tags: ["tokenization", "bpe", "cost", "fundamentals", "observability"]
prerequisites: []
produces:
  - "drills/day-001-tokens/tokviz.py"
  - "drills/day-001-tokens/pricing.py"
  - "costs.jsonl"
  - "notes/day-001.md"
objectives:
  - "Explain how BPE turns text into tokens, and why token count measures how surprising your text is to the tokenizer"
  - "Measure tokens-per-character across five text types on your own data rather than relying on the chars/4 heuristic"
  - "Use the authoritative token counter for each model and quantify the error of the wrong one"
  - "Explain why UUID-dense log lines are the worst-case input for an LLM system, in three independent respects"
  - "Stand up append-only cost logging designed to survive 180 days of schema needs"
---

# Day 1 — Tokenization and the real unit of cost

> Everything you build for the next six months is billed, budgeted, truncated, and degraded in units of tokens. Today you replace folklore with measurement.

**Phase 0 · Week 1 · Day 1 of 180 · Mode: learn**

---

## Learning objectives

By the end of today you can:

1. Explain how BPE turns text into tokens, and why token count is a direct measure of how *surprising* your text is to the tokenizer.
2. Measure tokens-per-character across five distinct text types on your own data.
3. Name the authoritative token counter for each model you use, and quantify the error of using the wrong one.
4. Explain why UUID-dense log lines are the worst-case input for an LLM system, in three independent respects.
5. Stand up append-only cost logging whose schema will still serve you on Day 180.

---

## Concept (40 min)

### 1. Why tokens exist at all

Three ways to feed text to a transformer, and why the industry landed where it did:

| Approach | Vocab size | Problem |
|---|---|---|
| **Characters** | ~100 | Sequences get enormous. Attention is O(n²) in sequence length. No semantic units to learn from. |
| **Words** | 100k–1M+ | Out-of-vocabulary explosion. `kubernetes` and `kubernetes,` are different tokens. Typos are unrepresentable. Morphology is lost. |
| **Subwords (BPE)** | 30k–200k | The compromise everyone uses. Common words are one token; rare words split into meaningful pieces; nothing is ever unrepresentable. |

Subword tokenization is a **compression scheme learned from a training corpus**. That last clause is the whole lesson: a tokenizer compresses well on text that looks like its training data, and badly on text that doesn't. Your production logs do not look like the training data.

### 2. How BPE actually works

Byte-Pair Encoding began as a compression algorithm (Gage, 1994) and was adapted for neural machine translation by Sennrich et al. (2016).

**Training** the tokenizer:

1. Start with a vocabulary of individual bytes (256 entries).
2. Count every adjacent pair of symbols across the corpus.
3. Merge the single most frequent pair into a new vocabulary entry.
4. Repeat until you hit the target vocab size.
5. Save the **ordered list of merges**.

**Encoding** new text: apply the learned merges, in the order they were learned.

The consequence: a sequence that occurred frequently during training gets merged into few tokens. A sequence that never occurred gets no merges and falls apart into short fragments.

> **Token count is a direct measure of how surprising your text is to the tokenizer.**

### 3. Byte-level BPE and the multilingual tax

Modern tokenizers are **byte-level** — they start from raw UTF-8 bytes rather than Unicode characters. This guarantees any text is encodable (no unknown token, ever), but creates a sharp asymmetry:

- ASCII characters are 1 byte each.
- Devanagari (Hindi, Marathi), Tamil, and most non-Latin scripts are **3 bytes each** in UTF-8.
- If the training corpus was English-dominant, the tokenizer learned few merges for those byte sequences.

So Devanagari text can cost several times more tokens per character than equivalent English. This is a real cost multiplier and a real **context window shrinkage** for non-English workloads — which is why you're feeding an Indic-script sample through your tool today rather than taking my word for it.

### 4. Five failure modes that are actually tokenization

| Failure | Mechanism |
|---|---|
| **Arithmetic errors** | Numbers tokenize inconsistently — `1234` may be one token while `1235` splits as `123`+`5`. The model never sees consistent place value. This is why digit-by-digit prompting helps, and why some newer tokenizers force fixed-size digit groups deliberately. |
| **Structured output breakage** | Token boundaries don't respect JSON syntax. `{"` may be a single token; an unusual key like `svc_id_v2` fragments unpredictably. Critical for constrained decoding (Day 8), where a grammar operates over *tokens*, not characters. |
| **Non-English degradation** | §3. Same prompt, same meaning, several times the cost and a fraction of the effective context. |
| **Wrong cost estimates** | The chars/4 rule is roughly right for English prose and badly wrong for everything else. |
| **Context exhaustion** | Your context window holds far less log data than you estimated, because logs are the worst case. |

### 5. Why UUIDs are the most expensive text you will ever send

Take `550e8400-e29b-41d4-a716-446655440000` — 36 characters.

It is high-entropy hexadecimal. BPE merges encode *statistical regularity*, and random hex has none. The tokenizer finds no learned merges and falls back to short fragments — typically 15–25 tokens for that single UUID, somewhere around 1.5–2.4 chars/token.

Three problems compound:

1. **Incompressible.** Maximum tokens for the byte count.
2. **Semantically empty.** The model cannot reason about a UUID beyond string matching. You pay premium prices for content carrying no meaning it can use.
3. **They cluster.** One production log line often carries a trace ID, a span ID, a request ID, an ISO-8601 timestamp (also poorly compressed), an IP address, and sometimes a content hash.

A 200-character log line can cost 80–100 tokens where 200 characters of English prose costs around 50.

> **This is the central fact of SENTINEL's economics.** Incident response is a workload made almost entirely of the most token-expensive text that exists. Every retrieval decision in Phase 2, the compaction work on Day 33, and the entire cost argument in Phase 5 trace back to this.

---

## Guidance

### The tokenizer trap you must not fall into

**`tiktoken` is OpenAI's tokenizer. It is wrong for Claude.**

It undercounts Claude tokens by roughly 15–20% on ordinary prose, and considerably more on code and non-English text. Any Claude cost estimate derived from `tiktoken`, `gpt-tokenizer`, or a chars/4 heuristic is wrong — usually in the direction that flatters your budget.

For Claude, the authoritative count comes from the API:

```python
from anthropic import Anthropic

client = Anthropic()
resp = client.messages.count_tokens(
    model="claude-opus-5",
    messages=[{"role": "user", "content": text}],
)
print(resp.input_tokens)
```

There is also a CLI, useful for quick checks:

```bash
ant messages count-tokens --model claude-opus-5 --message '{role: user, content: "@./sample.txt"}' --transform input_tokens -r
```

### Token counts belong to a (text, model) pair — not to text

**Pass the same model ID you will actually call.** This is not a formality. Claude's tokenizer changed between model generations, and the same text produces materially different counts across models *within the same family* — Claude Sonnet 5 produces roughly 30% more tokens for the same text than Sonnet 4.6 did.

A budget calibrated on one model does not transfer to its successor. Sit with that: **"how many tokens is this?" has no model-independent answer.**

### Three tokenizers, three distinct roles

| Tokenizer | Role | Why |
|---|---|---|
| `messages.count_tokens` | **Ground truth for Claude** | The only correct source. Model-specific. |
| HF `AutoTokenizer` (Llama 3.1 8B) | **Ground truth for your local model** | The actual tokenizer. Also exposes token boundaries you can visualize. |
| `tiktoken` | **The folklore estimator under test** | Not for costing. You are measuring how wrong it is. |

That third row is the point of the exercise, not a shortcut.

### Design note: `costs.jsonl` is a 180-day commitment

Every model call from today until Day 180 appends one line. On Day 177 you reconstruct six months of cost history from this file. Retrofitting fields onto six months of untagged data is not possible — get the schema right now.

Two fields people omit and later need:

- **Cache token fields.** `input_tokens` is the *uncached remainder only*. Total prompt size is `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`. Record all three or your Phase 5 cache analysis will be silently wrong.
- **`ttft_ms`.** Day 2 needs it; Phase 5 lives on it. Capture it from today even though today's calls aren't streaming.

---

## Practical (80 min)

### Setup

```bash
mkdir -p drills/day-001-tokens/samples && cd drills/day-001-tokens
uv add anthropic tiktoken transformers rich
```

### Build

**`tokviz.py`** — a CLI taking one or more files, reporting per file:

- Character count and byte count (they differ; that difference is the point for the Indic sample)
- Claude token count via `count_tokens`, for **two different Claude models**
- Local model token count via `AutoTokenizer`
- `tiktoken` estimate and its **percentage error versus the Claude ground truth**
- tokens-per-character and characters-per-token for each tokenizer
- Estimated input and output cost at current rates
- A visualization of token boundaries

**`pricing.py`** — a rate table with a `last_verified` date. Not scattered constants.

| Model | Model ID | Input $/1M | Output $/1M |
|---|---|---|---|
| Claude Opus 5 | `claude-opus-5` | $5.00 | $25.00 |
| Claude Sonnet 5 | `claude-sonnet-5` | $3.00 ($2.00 introductory, through 2026-08-31) | $15.00 ($10.00 intro) |
| Claude Haiku 4.5 | `claude-haiku-4-5` | $1.00 | $5.00 |

Verify against the pricing page before hardcoding. Note Sonnet 5's introductory rate expires in eleven days — your cost model has an expiry date, which is itself worth internalizing on Day 1.

**The five samples** in `samples/`, chosen to span the range you'll actually meet:

| File | Content | What it isolates |
|---|---|---|
| `prose.txt` | ~500 words of ordinary English | The baseline the folklore was built on |
| `sample.py` | A real Python file, 100+ lines | Punctuation density, indentation, identifiers |
| `payload.json` | Nested JSON, realistic keys | Structural token overhead |
| `logline.txt` | 20 real-shaped log lines: trace IDs, span IDs, ISO timestamps, IPs | **The SENTINEL case** |
| `devanagari.txt` | ~200 words of Marathi or Hindi | The multilingual tax |

Write `logline.txt` in the shape your services actually emit. A toy example makes the headline number meaningless.

**`costs.jsonl`** — append-only, one line per model call, never rewritten:

```json
{
  "ts": "2026-08-20T14:32:11.482Z",
  "run_id": "01J...",
  "day": 1,
  "phase": 0,
  "component": "drill",
  "provider": "anthropic",
  "model": "claude-opus-5",
  "input_tokens": 1234,
  "output_tokens": 56,
  "cache_creation_input_tokens": 0,
  "cache_read_input_tokens": 0,
  "ttft_ms": 210,
  "latency_ms": 842,
  "cost_usd": 0.00757,
  "tags": {"drill": "day-001-tokens", "sample": "logline.txt"}
}
```

`component` and `tags` feed Day 112's cost attribution; `run_id` correlates with OTel traces from Day 111.

### Visualizing token boundaries

Alternate background colors per token using ANSI escapes, or `rich`'s `Text` with per-span styles. Decode each token individually and print with alternating styles.

**The gotcha you will hit:** byte-level BPE tokens can split *in the middle of a UTF-8 character*. Decoding a single token can produce invalid UTF-8. Decode with `errors="replace"` and log where it happens — then look at those positions in your Devanagari sample. You will literally see one character spread across multiple tokens. That is the multilingual tax rendered visible, and it teaches more than the ratio does.

### Acceptance criteria

- [ ] `tokviz.py samples/*.txt samples/*.py samples/*.json` runs and produces one row per file per tokenizer
- [ ] Claude counts come from `count_tokens`, never from `tiktoken`
- [ ] Two Claude models are compared on identical input
- [ ] `tiktoken` error is reported as a percentage, per sample
- [ ] Token-boundary visualization renders, with UTF-8 split points flagged
- [ ] `pricing.py` carries a `last_verified` date
- [ ] `costs.jsonl` exists with all three token-count fields populated
- [ ] `notes/day-001.md` records the four numbers under *Proof of understanding*

---

## Challenge

*Optional. Attempt if the practical took under 80 minutes — or come back to it on your Day 6 consolidation.*

### Build a UUID aliaser and measure what it buys

The concept section named a mitigation: replace high-entropy identifiers with short symbolic handles before they reach the model, and keep a lookup table on your side. The model was only ever doing string correlation on those values — it can correlate `trace_A` just as well as `550e8400-e29b-41d4-a716-446655440000`, at a fraction of the cost.

Build it:

1. Detect UUIDs, hex hashes, ISO-8601 timestamps, and IP addresses in your `logline.txt` sample.
2. Replace each *distinct* value with a stable short handle — `trace_A`, `span_B`, `ts_1`, `ip_1` — maintaining a bidirectional lookup table.
3. Re-measure token count on the aliased text.
4. Report the reduction as a percentage, and as dollars per 1,000 log lines at Opus 5 input rates.

Then verify it actually preserves capability — this is the part that makes it a real experiment rather than a compression trick:

5. Take an aliased log excerpt where two lines share a trace ID. Ask a model a question that requires correlating them ("which service handled the same request as the auth failure?").
6. Ask the same question over the un-aliased excerpt.
7. Confirm the answers agree.

**Success looks like:** a stated percentage token reduction, a dollar figure per 1,000 lines, and a demonstrated correlation task that survives aliasing.

**Stretch:** find the failure case. Construct an input where aliasing *loses* information the model needed — a timestamp whose actual value mattered for ordering, or an IP whose subnet was diagnostically relevant. Name the rule you'd use to decide what is safe to alias. That rule is the deliverable, and it's what Day 33's compaction work will build on.

---

## Proof of understanding

You are done when you can state, from your own measurements, all four:

### 1. The five ratios

Tokens-per-character for each sample, on the same model. Approximate expectations — **measure, don't trust these**:

| Sample | ~chars/token | ~tokens/char |
|---|---|---|
| English prose | 4.0 | 0.25 |
| Python code | 3.0–3.5 | 0.29–0.33 |
| JSON | 2.8–3.2 | 0.31–0.36 |
| Log lines with UUIDs | 1.7–2.2 | 0.45–0.59 |
| Devanagari | 1.0–1.5 | 0.67–1.0 |

If your log-line ratio isn't roughly 2× worse than your prose ratio, check whether your sample contains realistic identifiers.

### 2. The `tiktoken` error

Percentage error versus `count_tokens`, per sample. Note which sample it's worst on. This is why you will never estimate Claude costs with a non-Claude tokenizer.

### 3. The cross-model delta

Same text, two Claude models, two counts. State the percentage difference and what it implies for a budget you calibrated last quarter.

### 4. The UUID explanation

Explain, unprompted, why log lines full of UUIDs are the most expensive text you will ever put in a context window. The complete answer has three parts — incompressibility, semantic emptiness, clustering — and connects to why SENTINEL's retrieval budget in Phase 2 is a hard constraint rather than a nice-to-have.

Write all four into `notes/day-001.md`.

---

## Common traps

| Trap | Consequence |
|---|---|
| Costing with `tiktoken` | 15–20%+ underestimate. The trap this lesson exists to prevent. |
| Recording only `input_tokens` | Misses cached tokens; silently breaks Phase 5 cache analysis. |
| Hardcoding prices inline | They change — Sonnet 5's intro rate expires this month. |
| A toy log sample | The headline number becomes meaningless. |
| Assuming counts transfer across models | They don't, even within one family. |
| Skipping the visualization | You miss the most instructive artifact of the day. |

---

## References

| Source | Why |
|---|---|
| "Neural Machine Translation of Rare Words with Subword Units" — Sennrich, Haddow & Birch (2016) | The BPE paper. §3.2 is the algorithm. |
| "Language Models are Unsupervised Multitask Learners" — Radford et al. (2019) | §2.2 covers byte-level BPE and why it eliminates the unknown token. |
| Anthropic token counting documentation | The `count_tokens` endpoint reference. |
| Anthropic pricing page | Verify rates rather than trusting any table, including the one above. |
| `tiktoken` repository documentation | Read it to understand BPE encoding mechanics — then never use it to count Claude tokens. |

---

## Navigation

**Phase:** [Phase 0 — Foundations & Mental Models](../phase-00-foundations.md)
**Next:** [Day 2 — Transformer inference: prefill, decode, and the KV cache](day-002-inference.md)

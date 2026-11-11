---
day: 2
phase: 0
week: 1
title: "Transformer inference: prefill, decode, and the KV cache"
slug: "day-002-inference"
mode: "learn"
duration_min: 120
concept_min: 40
practical_min: 80
capstone_version: null
deliverable: null
tags: ["inference", "latency", "prefill", "decode", "kv-cache", "ttft", "benchmarking"]
prerequisites: [1]
produces:
  - "drills/day-002-inference/phases.py"
  - "drills/day-002-inference/plot.py"
  - "drills/day-002-inference/runs.jsonl"
  - "drills/day-002-inference/plots/ttft-vs-prompt.png"
  - "drills/day-002-inference/plots/decode-vs-output.png"
  - "notes/day-002.md"
objectives:
  - "Explain why prefill is compute-bound and decode is memory-bandwidth-bound, and what each implies for latency"
  - "Explain what the KV cache stores, why it turns decode from quadratic into linear work, and why its size caps concurrency"
  - "Measure TTFT against prompt length and decode time against output length on your own hardware, and state both slopes with units"
  - "Predict your decode speed ceiling from model size and memory bandwidth before measuring it, then explain the gap"
  - "Explain why a long prompt with a short answer and a short prompt with a long answer have opposite cost and latency profiles"
---

# Day 2 — Transformer inference: prefill, decode, and the KV cache

> Yesterday you learned what a token costs. Today you learn that not all tokens cost the same *time* — and that one architectural fact explains almost every latency number you will meet for the next six months.

**Phase 0 · Week 1 · Day 2 of 180 · Mode: learn**

---

## Learning objectives

By the end of today you can:

1. Explain why prefill is compute-bound and decode is memory-bandwidth-bound, and what each implies for latency.
2. Explain what the KV cache stores, why it turns decode from quadratic work into linear work, and why its size — not the model weights — is what usually caps concurrency.
3. Measure time-to-first-token against prompt length and decode time against output length on your own hardware, and state both slopes with units.
4. Predict your decode speed ceiling from model size and memory bandwidth *before* measuring it, and explain the gap.
5. Explain why a long prompt with a short answer and a short prompt with a long answer have opposite cost and latency profiles.

---

## Concept (40 min)

### 1. One request, two completely different machines

Generating a response is not one operation. It is two, and they have almost nothing in common.

| | **Prefill** | **Decode** |
|---|---|---|
| What it does | Processes the entire prompt | Generates one token, then the next, then the next |
| Parallelism | All prompt tokens at once | Strictly sequential — token *n* needs token *n−1* |
| Linear algebra | Matrix × **matrix** | Matrix × **vector** |
| Bottleneck | **Compute** (FLOPs) | **Memory bandwidth** (bytes/s) |
| Scales with | Prompt length | Output length |
| Governs | Time-to-first-token (TTFT) | Time-per-output-token (TPOT) |
| GPU utilisation | Excellent | Dreadful |
| Happens | Once | Once per output token |

The whole day is contained in row 4. Prefill is limited by how fast your hardware can multiply; decode is limited by how fast it can *read*. These are different numbers on every piece of silicon you will ever use, and they differ by an order of magnitude or more.

The latency model that falls out of this is the one you will use for the rest of the curriculum:

> **latency ≈ TTFT(prompt_length) + output_tokens × TPOT**

Two terms. Two different physical limits. Two different slopes to measure. That is today's practical.

### 2. Why decode is bandwidth-bound (the arithmetic that surprises people)

To produce **one** output token, the GPU must read **every parameter of the model** out of memory and into the compute units. All of them. For one token.

An 8B model at 4-bit is roughly 4.7 GB of weights. Producing one token means moving 4.7 GB. Producing 500 tokens means moving 2.35 *terabytes* — through the same weights, 500 times.

So there is a hard floor on decode speed that has nothing to do with how fast your chip can do arithmetic:

```
TPOT_floor (seconds/token) ≈ model_bytes / memory_bandwidth
tokens/sec_ceiling          ≈ memory_bandwidth / model_bytes
```

Worked example — a 4.7 GB model on hardware with 400 GB/s:

```
4.7 GB / 400 GB/s = 11.75 ms per token  →  ~85 tokens/sec, absolute ceiling
```

Now count the arithmetic done during that 11.75 ms: about 2 × 8e9 = 16 GFLOP. A chip capable of tens of TFLOP/s finishes that in well under a millisecond and then waits. **Arithmetic intensity during decode is roughly 1 FLOP per byte moved** — which is why a GPU can report 100% "utilisation" while doing almost no useful floating-point work. Day 121 makes you compute that percentage explicitly; today you only need to believe the shape of it.

Three consequences worth carrying:

- **Decode speed is predictable from a spec sheet.** You can estimate tokens/sec for a model on hardware you have never touched. You will do this today, before you measure.
- **Quantization buys decode speed, not just memory.** Halving bytes-per-parameter halves the bytes moved per token. That is Day 11 and Day 127.
- **Batching is nearly free for decode.** The weights get read once and serve every sequence in the batch. Eight concurrent requests cost barely more wall-clock per step than one. This is the single reason serving systems exist, and it is Day 123.

Prefill has the opposite character: it does the same weight read but amortises it across *all* prompt tokens at once, so it is doing thousands of FLOPs per byte moved. It saturates compute instead. Which is why, per token, **prefill is typically 10–50× faster than decode on the same hardware** — the number you are about to measure.

### 3. The KV cache: what it is and why decode isn't quadratic

Attention at step *n* needs the key and value vectors of every preceding token. The naive implementation recomputes K and V for the whole sequence at every step — making generation of *N* tokens O(N²) in work over the prompt and everything generated so far. It would be unusably slow.

So every inference engine caches them. **The KV cache stores the key and value vectors for every token processed so far, at every layer.** Prefill fills it in one shot. Each decode step appends exactly one token's worth and reads the rest.

That turns per-step work from "recompute everything" into "read the cache." Decode becomes linear. This is not an optimisation you can decline — it is the reason decode is viable at all.

The price is memory, and the formula is worth memorising now because Days 11, 122 and 133 all run on it:

```
kv_bytes = 2 × layers × kv_heads × head_dim × seq_len × bytes_per_element
           ^
           K and V
```

Note **`kv_heads`, not `heads`.** Grouped-query attention (GQA) lets many query heads share one KV head, and it exists almost entirely to shrink this number — often by 4–8×. If you compute KV cache size using the query head count you will overestimate badly on any modern model.

Two facts follow, and they are the backbone of Phase 5:

1. **The KV cache grows linearly with context length, per sequence.** Long-context serving is expensive in a way the per-token price does not advertise.
2. **It is usually the KV cache, not the weights, that caps concurrency.** Weights are loaded once and shared. Cache is per-request. Your maximum concurrent sequences ≈ (VRAM − weights − activations) / kv_bytes_per_sequence. That is the number Day 122 asks you to derive and then break by OOMing your own GPU.

The vLLM paper (your reference today) exists because naive implementations pre-allocate KV cache for the maximum possible sequence length per request, and then waste 60–80% of it. PagedAttention manages the cache in fixed-size blocks like OS virtual memory pages. Read sections 2–3 for the problem statement; you do not need section 4 yet.

### 4. The prefill quadratic nobody mentions

"Prefill is linear in prompt length" is a useful lie. Prefill FLOPs have two terms:

```
weights term:    2 × params × P              (linear in P)
attention term:  4 × layers × d_model × P²   (quadratic in P)
```

The ratio of the second to the first is:

```
attention_share ≈ 2 × layers × d_model × P / params
```

For a 7B model with 28 layers and d_model 3584, the terms are equal at **P ≈ 38,000 tokens**. At P = 16k — the top of today's matrix — the attention term is about **43%** of the weights term.

So the honest prediction for your plot is: *linear plus a quadratic term that is invisible at 1k, mild at 16k, and dominant at 128k.* If your 16k point sits noticeably above the line fitted through 100/1k/4k, that is not measurement noise. That is O(n²) becoming visible on your own laptop, and it is exactly why Day 4's long-context work and Phase 2's retrieval budget are not optional.

FlashAttention reduces the *memory traffic* of that term, not its FLOPs. The quadratic does not go away.

### 5. Why the API charges input and output differently

Yesterday's `pricing.py` has output priced at 5× input on every Claude model. That is not a margin decision, it is this lesson showing up on an invoice:

| | Prefill (input) | Decode (output) |
|---|---|---|
| Parallelisable | Yes, fully | No, inherently serial |
| Batches well | Somewhat | Extremely — but only in the token dimension |
| GPU time per token | Low | High |
| Bills at | 1× | ~5× |

And it is why **prompt caching** is the highest-leverage optimisation available to an agent: a cached prefix skips prefill entirely. Yesterday you provisioned `cache_creation_input_tokens` and `cache_read_input_tokens` in `costs.jsonl` without using them. Today's challenge is where they earn their place — a cache read bills at 0.1× input *and* produces a dramatically lower TTFT, because the prefill for that prefix already happened. Day 130 does this at the serving layer; Day 136 does it semantically.

### 6. What this means for an agent loop

An agent turn is not one request. It is a chain: prompt → tool call → tool result appended → prompt again → tool call → … Each hop re-prefills a context that grew by the tool result, and produces a short burst of output tokens.

So agent latency is dominated by **prefill repeated over a growing context**, not by generation. Three things follow, each of which becomes a whole day later:

- The system prompt and tool definitions are identical on every hop — perfect prefix-cache material (Day 130).
- Tool results that bloat context are paying a prefill tax *on every subsequent hop*, not once. That compounding is why Day 33 spends a day on compaction.
- Streaming does not make anything faster, but it changes which number the user experiences — TTFT instead of total latency (Day 31).

> **The distinction you are measuring today is the one that makes Phase 5 derivable rather than memorisable.** Continuous batching, PagedAttention, speculative decoding, chunked prefill, prefix caching, cascade routing — every one of them is an attempt to make decode look more like prefill, or to avoid doing prefill twice.

---

## Guidance

### Wall-clock TTFT is not prefill time

Your stopwatch measures: HTTP round trip + request queueing + tokenizer + **prefill** + first-token sampling + detokenization + stream flush. Prefill is one term among several, and the others are roughly constant.

That constant is *not* noise to be eliminated — it is the intercept of your fit, and on a short prompt it can be most of your TTFT. Report it. `TTFT = a + b × P` where `a` is framework overhead and `b` is your prefill rate.

Ollama gives you the engine's own view for free, so you can separate them. Every `/api/generate` response carries nanosecond timings:

| Field | Meaning |
|---|---|
| `load_duration` | Model load. Huge on the first call, ~0 when warm. Warm up or your first row is garbage. |
| `prompt_eval_count` | Prompt tokens actually processed |
| `prompt_eval_duration` | **Pure prefill time** |
| `eval_count` | Output tokens actually generated |
| `eval_duration` | **Pure decode time** |
| `total_duration` | Everything |

`wall_clock_ttft − prompt_eval_duration` is your framework overhead, measured rather than assumed. Record both.

> **If `prompt_eval_count` is missing or implausibly small, your prompt was served from cache.** That is the single most valuable diagnostic in this drill — see the traps below.

### Set the context window explicitly, or the 16k row is a lie

Ollama defaults `num_ctx` to a few thousand tokens regardless of what the model supports. Send a 16k-token prompt without setting it and the prompt is **silently truncated** — no error, no warning, and a TTFT that looks suspiciously flat at the top of your range.

Set it on every request, above prompt + output:

```python
options = {"num_ctx": 24576, "num_predict": n_out, "temperature": 0}
```

Keeping `num_ctx` constant across the whole matrix also removes a confound: KV cache allocation changes with context size, and you want one variable moving at a time.

### Build prompts to an exact *token* length

Day 1's entire lesson was that characters are not tokens and the ratio depends on content. So do not build a "4k prompt" out of 16,000 characters. Tokenize, slice to the exact count, decode back, verify with a second tokenize. Use the same `AutoTokenizer` path you built yesterday — `drills/day-001-tokens/tokviz.py` already has the Ollama-tag → HF-repo mapping you need.

And use **realistic filler**, not `"token " * 4000`. Repetitive text is unusually cheap to tokenize and behaves oddly in cache. Your `logline.txt` and `prose.txt` samples from yesterday are right there, and log lines are what SENTINEL will actually prefill.

### Do not assume the model produced the tokens you asked for

`num_predict: 500` is a *cap*, not a target. The model will emit EOS when it decides it is done, and your "500 output tokens" row will quietly be 60. Two options:

1. Prompt for output that does not want to stop ("List the integers from 1 to 400, one per line, no commentary"), and
2. **Always divide by the measured `eval_count`, never by the requested `num_predict`.**

Do both. Option 2 is what makes the data honest.

### Measure per-token, fit on the aggregate

Each cell needs repeats — 3 minimum, 5 is better — with the first discarded as warm-up. Report the **median**, not the mean; a single background process on a laptop produces outliers that drag a mean around and tell you nothing about the machine.

### Predict before you measure

Before running anything, compute your decode ceiling from §2 and write the number down:

```
tokens/sec_ceiling ≈ memory_bandwidth / model_bytes
```

On Apple Silicon, memory bandwidth is the unified-memory figure for your specific chip (they range from roughly 100 to 800 GB/s across the M-series tiers) — look yours up rather than guessing. On an NVIDIA card it is the HBM/GDDR bandwidth from the spec sheet. Model bytes is the size of the GGUF file on disk, near enough.

A prediction you wrote down before measuring is worth ten explanations you construct afterwards. The gap between your prediction and your measurement is the interesting part of today.

---

## Practical (80 min)

### Setup

```bash
mkdir -p drills/day-002-inference/plots && cd drills/day-002-inference
uv add httpx matplotlib numpy rich
ollama list          # pick the model you will use all phase
```

Use one model for the entire matrix. Mixing models mid-run invalidates both slopes.

### Build

**`phases.py`** — runs the matrix and appends one JSON line per run.

- Prompt lengths **{100, 1k, 4k, 16k} tokens** × output lengths **{10, 100, 500} tokens** = 12 cells
- `--repeats 5`, first discarded as warm-up
- Streams the response so TTFT is the arrival time of the first token, measured with `time.perf_counter()`
- **Randomises the prompt prefix per run** so nothing is served from cache (see traps)
- Records both wall-clock timings and Ollama's engine timings
- Prints a 4×3 table of median total latency, and a second of TTFT

One line per run in `runs.jsonl`:

```json
{
  "ts": "2026-09-11T09:14:03.221Z",
  "run_id": "01J...",
  "day": 2,
  "phase": 0,
  "component": "drill",
  "provider": "ollama",
  "model": "qwen2.5:7b-instruct",
  "num_ctx": 24576,
  "prompt_tokens_requested": 4096,
  "prompt_tokens_actual": 4096,
  "output_tokens_requested": 100,
  "output_tokens_actual": 100,
  "repeat": 2,
  "ttft_ms": 612,
  "total_ms": 3840,
  "decode_ms": 3228,
  "prefill_ms_engine": 548,
  "decode_ms_engine": 3201,
  "load_ms_engine": 0,
  "overhead_ms": 64,
  "tpot_ms": 32.28,
  "prefill_tok_per_s": 7474,
  "decode_tok_per_s": 30.9,
  "tags": {"drill": "day-002-inference", "cell": "p4096-o100"}
}
```

Same shape as `costs.jsonl` — `ts`, `run_id`, `day`, `phase`, `component`, `tags` — because Day 112 wants to join across both and Day 111 wants to correlate `run_id` with trace IDs. Local runs cost $0, so they do not belong in `costs.jsonl`; the schema still does.

**`plot.py`** — reads `runs.jsonl` and produces two figures plus a fit:

1. **`plots/ttft-vs-prompt.png`** — TTFT (y) against prompt tokens (x), one series per output length. The three series should lie on top of each other. Fit `TTFT = a + b × P`; report `a` in ms and `b` in ms per 1k prompt tokens.
2. **`plots/decode-vs-output.png`** — (total − TTFT) (y) against output tokens (x), one series per prompt length. Fit `decode = c + d × N`; report `d` in ms/token — that is TPOT.

Print the two slopes with units, converted into throughput:

```
prefill:  1000 / b  tokens/sec
decode:   1000 / d  tokens/sec
ratio:    prefill ÷ decode
```

### The independence check (do not skip this)

Two cross-checks that catch harness bugs:

- **TTFT must not depend on output length.** It cannot, causally — the first token arrives before the rest exist. If your three TTFT series separate, your timer is wrong or something is cached.
- **Decode time must be *nearly* independent of prompt length.** Nearly. Compare TPOT at 16k prompt against TPOT at 100 prompt. It will be higher — every decode step reads a KV cache 160× larger. Expect a few percent to ~20% depending on the model and engine. **That residual is the KV cache, measured.** It is the only direct evidence of the cache you will get today, and it is the single best number in the drill.

### Acceptance criteria

- [ ] `runs.jsonl` has ≥ 60 lines (12 cells × 5 repeats), warm-up runs flagged and excluded from fits
- [ ] `num_ctx` is set explicitly and `prompt_tokens_actual` matches `prompt_tokens_requested` at every cell — including 16k
- [ ] Per-token rates are computed from **measured** `eval_count`, never from `num_predict`
- [ ] Both plots render, with a fitted line and its equation on each
- [ ] Prefill slope and decode slope reported with units, plus their ratio
- [ ] Your predicted decode ceiling and your measured decode rate both appear in the notes, with the gap explained
- [ ] TPOT at 16k vs TPOT at 100 stated, as a percentage
- [ ] Engine-reported prefill time and wall-clock TTFT both recorded; framework overhead stated as a number
- [ ] `notes/day-002.md` answers all four *Proof of understanding* items

---

## Challenge

*Optional. Attempt if the practical took under 80 minutes — or save it for Day 6.*

### Measure what a cache hit is worth, twice

The concept section claims a cached prefix skips prefill. Prove it on both tiers.

**Local (prefix caching in the engine):**

1. Take your 16k prompt. Send it twice, back to back, with the *same* prefix.
2. Record TTFT for both. Check whether `prompt_eval_count` shrank or vanished on the second.
3. Now vary only the last 100 tokens and repeat. Then vary the *first* 100 tokens and repeat.
4. Report TTFT for all three conditions.

The third condition is the point: prefix caching matches from the **beginning** of the context. Change one token at position 0 and you have invalidated 16k tokens of cache. This is why the stable parts of a prompt — system instructions, tool definitions, few-shot examples — go first, and volatile content goes last. That ordering rule is worth more than the measurement.

**API (Anthropic prompt caching):**

5. Build a prompt with a long stable prefix and mark it with `cache_control`. Note the minimum cacheable prefix length in the docs — roughly 1024 tokens for Opus/Sonnet, more for Haiku — and check it, because a short prefix silently caches nothing and you will conclude the feature does not work.
6. Call twice. Log both to `costs.jsonl` with the schema you already have.
7. Confirm `cache_creation_input_tokens` on call one and `cache_read_input_tokens` on call two.
8. Report the TTFT delta **and** the cost delta, using `pricing.py`'s multipliers — write at 1.25×, read at 0.10×.

**Success looks like:** a stated break-even (how many cache reads pay for one cache write — it falls out as `0.25 / 0.90`, under a third of a call), a TTFT reduction in ms, and the ordering rule stated in one sentence.

**Stretch — the arithmetic that sizes SENTINEL:** compute the KV cache size per sequence for your local model at 4k, 32k and 128k context using §3's formula, taking `layers`, `kv_heads` and `head_dim` from the model's `config.json`. Then divide your available VRAM (minus weights) by it to get a maximum concurrency at each length. Sanity-check against `ollama ps` or `nvidia-smi`. You have just done Day 122's arithmetic 120 days early — and you now know the length at which SENTINEL's concurrency falls to 1.

---

## Proof of understanding

Write all four into `notes/day-002.md`, from your own numbers.

### 1. The two slopes

- Prefill: **___ ms per 1k prompt tokens** → ___ tokens/sec
- Decode: **___ ms per output token** → ___ tokens/sec
- Ratio: prefill is **___×** faster per token than decode
- Intercept `a`: **___ ms** of fixed overhead before prefill starts

State the R² of each fit. If the TTFT fit is poor, say whether the 16k point sits above the line — and connect that to §4.

### 2. Prediction versus measurement

Your predicted decode ceiling (`bandwidth / model_bytes`) against your measured decode rate. Expect to land somewhere between 50% and 90% of the ceiling. Explain the gap — candidate causes: attention reads the KV cache on top of the weights, sampling and detokenization are not free, quantized weights are dequantized on the fly, memory bandwidth is shared with everything else on the machine, and spec-sheet bandwidth is never achieved in practice.

An explanation that names which of these dominates for *your* setup is worth more than one that lists all five.

### 3. The two workloads

Fill this in from your matrix, then add API costs from yesterday's `pricing.py`:

| Workload | Prompt | Output | TTFT | Total | Local $ | Opus 5 $ |
|---|---|---|---|---|---|---|
| **A** — long prompt, short answer | 16k | 10 | | | $0 | |
| **B** — short prompt, long answer | 100 | 500 | | | $0 | |

Then answer, in your own words:

- Which has the worse TTFT, and which has the worse total latency? They are usually not the same workload.
- Which costs more on the API, and by how much? (Note that output bills at 5×, so token counts alone do not tell you.)
- Which one would batching help, and why only that one?
- SENTINEL's triage hop looks like A — a large evidence bundle in, a short verdict out. Its report-writing hop looks like B. **State what that implies for which hop you'd cache, which you'd batch, and which you'd stream.**

That last bullet is the day's real deliverable. Everything else is the evidence for it.

### 4. The KV cache, measured

TPOT at 16k prompt versus TPOT at 100 prompt, as a percentage increase. Explain the mechanism in one sentence — what extra bytes each decode step has to read, and why that number grows with context length but not with output length so far.

Then state: at what prompt length would that residual double your TPOT? You do not have to measure it; extrapolating from your own two points is the answer.

---

## Common traps

| Trap | Consequence |
|---|---|
| Leaving `num_ctx` at its default | The 16k prompt is silently truncated. Your prefill slope flattens at the top and your headline conclusion is wrong. The most expensive trap here. |
| Reusing the same prompt prefix across runs | The engine serves prefill from cache. TTFT collapses toward the intercept and you conclude prefill is free. Randomise the prefix — or run it deliberately once, to *see* it. |
| Not warming up | `load_duration` puts several seconds into your first cell. |
| Measuring prompt length in characters | Day 1 existed to prevent this. Your "4k prompt" is not 4k tokens. |
| Dividing by `num_predict` instead of `eval_count` | EOS fires early; your TPOT is inflated by however many tokens never happened. |
| Reporting means over few repeats | One background process moves the mean. Use medians. |
| Calling wall-clock TTFT "prefill time" | It includes queueing, HTTP and detokenization. Report the intercept separately. |
| Assuming decode is fully independent of prompt length | It is *nearly* independent. The residual is the KV cache, and it is the most interesting number in the drill. |
| Fitting a straight line through 16k without looking at the residual | You will miss the quadratic attention term becoming visible. |
| Using `"word " * n` as filler | Degenerate tokenization, degenerate cache behaviour. Use the Day 1 samples. |

---

## References

| Source | Why |
|---|---|
| "Efficient Memory Management for Large Language Model Serving with PagedAttention" — Kwon et al. (2023), **§2–3** | Today's set reading. §2 is the cleanest published description of prefill/decode and the KV cache; §3 quantifies how much cache memory naive allocation wastes. |
| "Efficiently Scaling Transformer Inference" — Pope et al. (2022) | The arithmetic-intensity and roofline treatment behind §2. You return to it on Day 121. |
| "GQA: Training Generalized Multi-Query Transformer Models" — Ainslie et al. (2023) | Why `kv_heads` ≠ `heads`, and what that buys. |
| "Fast Transformer Decoding: One Write-Head is All You Need" — Shazeer (2019) | The original argument that decode is memory-bound. Short, and still the clearest statement of it. |
| Ollama API documentation — `/api/generate` response fields | The timing fields in the Guidance table, and the `num_ctx` default that will bite you. |
| `llama-bench` (llama.cpp) | Benchmarks prompt processing (`pp`) and token generation (`tg`) as separate numbers — the professional version of today's drill. Run it afterwards and compare against your slopes. |
| Anthropic prompt caching documentation | Minimum cacheable prefix length and the cache-write/read multipliers, for the challenge. |

---

## Navigation

**Phase:** [Phase 0 — Foundations & Mental Models](../phase-00-foundations.md)
**Previous:** [Day 1 — Tokenization and the real unit of cost](day-001-tokenization.md)
**Next:** Day 3 — Sampling, determinism and reproducibility

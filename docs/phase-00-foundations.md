# Phase 0 — Foundations & Mental Models
**Days 1–12 · 2 weeks**

Not an introduction. These are the mechanics you will reach for every time an agent
behaves strangely at 11pm. Most engineers building agents cannot explain why their p99
latency is bad or why their JSON parsing fails 3% of the time. These twelve days are how
you stop being one of them.

**Phase deliverable:** *The cost & latency arithmetic every LLM app needs.*

---

## Week 1

### Day 1 — Tokenization and the real unit of cost
📖 **Full lesson: [day-001-tokenization.md](days/day-001-tokenization.md)**

**Concept (40 min)** — Models don't see characters or words; they see tokens produced by a
BPE-family tokenizer. Token boundaries explain a startling range of real bugs: arithmetic
failures, mangled non-English text, JSON that breaks on unusual keys, and cost estimates
that are wrong by 40%. Token counts are a property of the *pair* (text, model) — they
differ across model families and even across generations within one family.

**Practical (80 min)** — Build `drills/day-001-tokens/`: a CLI that takes a file and
reports token count, cost at current input/output rates, and a visualisation of the token
boundaries. Use three tokenizers — Anthropic's `messages.count_tokens` (ground truth for
Claude), a HuggingFace `AutoTokenizer` for your local model, and `tiktoken` *as the
folklore estimator under test*, never as a cost source. Feed it: English prose, a Python
file, a JSON blob, log lines with UUIDs and timestamps, and text in an Indic script. Set
up `costs.jsonl` logging now — every model call you make for the next 180 days appends to
it.

**Proof of understanding** — State the tokens-per-character ratio for each of your five
inputs; report `tiktoken`'s percentage error against `count_tokens` per sample; state the
count delta for the same text across two Claude models; and explain why log lines full of
UUIDs are the most expensive text you will ever put in a context window.

**Reference** — "Neural Machine Translation of Rare Words with Subword Units" (BPE);
"Language Models are Unsupervised Multitask Learners" §2.2 (byte-level BPE); Anthropic
token counting documentation. Note: `tiktoken` is OpenAI's tokenizer and undercounts
Claude by 15–20% — read it to learn BPE mechanics, never to cost a Claude call.

---

### Day 2 — Transformer inference: prefill, decode, and the KV cache
📖 **Full lesson: [day-002-inference.md](days/day-002-inference.md)**

**Concept (40 min)** — Inference has two phases with completely different performance
characteristics. Prefill processes your whole prompt in parallel — compute-bound, scales
with prompt length. Decode generates one token at a time — memory-bandwidth-bound, scales
with output length. The KV cache is what makes decode fast, and its size is what limits
how many concurrent requests a GPU can hold. Nearly every latency and capacity fact in
Phase 5 falls out of this one distinction.

**Practical (80 min)** — Empirically separate the two phases. Against a local model, run a
matrix: prompt lengths {100, 1k, 4k, 16k} × output lengths {10, 100, 500}. Record
time-to-first-token and total time for each cell. Plot TTFT against prompt length, and
(total − TTFT) against output length.

**Proof of understanding** — Your TTFT plot should be roughly linear in prompt length and
your decode time roughly linear in output length, largely independent of each other. Show
the two slopes. Explain from your data why a long prompt with a short answer and a short
prompt with a long answer have very different cost/latency profiles.

**Reference** — "Efficient Memory Management for Large Language Model Serving with
PagedAttention" (vLLM paper), sections 2–3.

---

### Day 3 — Sampling, determinism and reproducibility
**Concept (40 min)** — Temperature, top-p, top-k and min-p each reshape the output
distribution differently. `temperature=0` is *not* determinism — batching effects,
floating-point non-associativity on GPU and tie-breaking all produce run-to-run variance.
This matters enormously for agents: a non-reproducible failure is a failure you cannot
debug, and an eval suite with unmeasured variance produces conclusions that are noise.

**Practical (80 min)** — Take one prompt with a factual answer and one requiring
open-ended reasoning. For each, sample 20 completions at temperature ∈ {0, 0.3, 0.7, 1.0}.
Measure: exact-match rate at each temperature, and semantic variance (embed the outputs,
report mean pairwise distance). Then run the temperature-0 case 20 times and count distinct
outputs.

**Proof of understanding** — Report how many distinct outputs you got from 20 runs at
temperature 0. If it is more than 1 — and it usually is — you now know why "just set
temperature to zero" is not an eval strategy. Quantify the variance you must design around.

**Reference** — "The Curious Case of Neural Text Degeneration" (nucleus sampling);
your provider's documentation on determinism guarantees.

---

### Day 4 — Context window mechanics and positional degradation
**Concept (40 min)** — A model's advertised context length is a capacity limit, not a
performance guarantee. Retrieval accuracy varies substantially with *where* in the context
the relevant information sits, typically strongest at the beginning and end and weakest in
the middle. This single fact dictates prompt layout, RAG chunk ordering, and how much
conversation history is worth keeping.

**Practical (80 min)** — Build your own needle-in-a-haystack harness in
`drills/day-004-context/`. Generate filler text at lengths {2k, 8k, 32k, 100k} tokens,
insert a specific retrievable fact at 11 evenly-spaced depths, and ask the model to
retrieve it. Run against both a local 8B model and a frontier model. Produce a heatmap:
context length × needle depth → accuracy.

**Proof of understanding** — Produce *your* degradation curve, not one from a paper.
State the context length at which your local model's mid-context accuracy first drops
below 90%, and how that compares to the frontier model. This number governs every
retrieval decision you make in Phase 2.

**Reference** — "Lost in the Middle: How Language Models Use Long Contexts."

---

### Day 5 — **[BUILD]** Repo bootstrap and the SENTINEL spec
**Concept (40 min)** — Re-read [capstone-sentinel.md](capstone-sentinel.md) properly. A
capstone without a written spec becomes a pile of drills. Write down what "done" means
before you have any emotional investment in a particular architecture.

**Practical (80 min)** — Scaffold the `sentinel/` tree from [setup.md](setup.md). Write
`sentinel/SPEC.md` in your own words: problem statement, non-goals, the eight success
metrics with *your* target numbers, and your current guess at the architecture. Wire the
Day 1 cost logger and the Day 2 latency profiler into `sentinel/observability/` — they
become permanent infrastructure, not drill code.

**Proof of understanding** — Your spec names a target for **false confidence rate** and a
target for **time to hypothesis (p95)**. Both will be wrong. Writing them down anyway is
the point — Day 180 compares against them.

**Reference** — Your own `my-bio.txt`. The capstone should stretch past what you have
already shipped.

---

### Day 6 — **[CONSOLIDATE]** The cost and latency arithmetic
**Concept (40 min)** — Assemble Days 1–4 into a single model you can compute in your head:
cost = (input tokens × input rate) + (output tokens × output rate); latency ≈ TTFT(prompt
length) + output tokens × TPOT. Every architectural decision for the next six months gets
checked against this.

**Practical (80 min)** — Build `drills/day-006-budget/`: a calculator that takes a
proposed agent design (number of steps, average prompt and completion size per step, model
per step) and outputs expected cost and p50/p95 latency per task. Sanity-check it against
your real `costs.jsonl` data. Then write `notes/day-006.md` reviewing the week.

**Proof of understanding** — Use the calculator to estimate cost and latency for a
10-step SENTINEL investigation on a frontier model. If that number is uncomfortable,
good — Phase 5 exists to fix it, and you now have the baseline it will be measured against.

**Reference** — Your own `costs.jsonl`.

---

## Week 2

### Day 7 — Embedding geometry and why cosine similarity misleads
**Concept (40 min)** — Embeddings map text to vectors where distance approximates semantic
relatedness — but "related" is not "relevant," and it is definitely not "answers the
question." Embedding spaces are anisotropic (vectors cluster in a narrow cone, so raw
cosine scores compress into a narrow band), and similarity is dominated by topic and style
rather than by whether one text answers the other.

**Practical (80 min)** — Embed 200 sentences across 5 topics. Compute the full pairwise
cosine matrix. Report the score distribution — note how narrow it is. Then construct 10
adversarial pairs: (a) a question and its correct answer, phrased with no shared
vocabulary; (b) a question and a wrong-but-topically-identical passage. Check whether
cosine ranks (a) above (b).

**Proof of understanding** — Show at least one case where a semantically wrong passage
outscores the correct answer. You have just discovered, empirically, why Phase 2 spends
five days on hybrid search and reranking instead of trusting a vector store.

**Reference** — "SimCSE: Simple Contrastive Learning of Sentence Embeddings" (anisotropy
discussion); MTEB leaderboard methodology.

---

### Day 8 — Structured output and constrained decoding
**Concept (40 min)** — There are three tiers of reliability for getting structured data
out of a model: asking nicely and parsing (fails at scale), tool/function-call formats
(good), and true constrained decoding where a grammar or FSM masks the logits so invalid
tokens are literally impossible (near-perfect, with a quality cost when the schema fights
the model's natural output). Knowing which tier you're on tells you whether you need a
repair loop.

**Practical (80 min)** — Define a moderately nasty schema — nested objects, an enum, an
optional array, a field that must be one of 12 service names. Get it out of a model three
ways: (1) prompt + `json.loads` + retry, (2) tool-calling, (3) constrained decoding via
Outlines or llama.cpp's GBNF grammars. Run 100 samples through each. Measure parse success
rate, semantic correctness, and latency.

**Proof of understanding** — Report the three success rates and the latency penalty of
constrained decoding. Then find a case where constrained decoding produces *valid but
worse* output — forcing the schema can suppress reasoning the model wanted to do first.

**Reference** — "Efficient Guided Generation for Large Language Models" (Outlines);
llama.cpp GBNF grammar documentation.

---

### Day 9 — Prompt as program: instruction hierarchy and CoT failure modes
**Concept (40 min)** — Treat a prompt as code with a defined precedence order: system
instructions > developer instructions > user input > tool results > retrieved documents.
Trust decreases down that list, and Phase 7's entire security model depends on you having
internalised it now. Separately: chain-of-thought reliably helps on multi-step reasoning
and reliably *hurts* on tasks where the model's first instinct was right — and stated
reasoning is often post-hoc rationalisation rather than a faithful account of the
computation.

**Practical (80 min)** — Build a 30-task set spanning three categories: multi-step
arithmetic/logic, direct factual recall, and pattern completion. Run each with and without
CoT. Then take 10 CoT outputs where the answer was *wrong* and read the reasoning
carefully — classify whether the reasoning contains the error or whether the reasoning is
correct and the final answer diverges from it.

**Proof of understanding** — Name the task category where CoT made accuracy *worse*, with
numbers. And report how many of your 10 wrong answers had *correct* reasoning attached —
that gap is why "the agent explained itself" is not evidence the agent was right.

**Reference** — "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models";
"Language Models Don't Always Say What They Think."

---

### Day 10 — The model landscape and honest selection
**Concept (40 min)** — Public benchmarks are contaminated, gamed, and rarely predictive of
your task. The only benchmark that matters is one built from your own data. What you
actually need is a decision procedure: capability tier required, latency budget, cost
ceiling, data residency constraint, context length needed, structured-output support, tool
calling quality — then the smallest and cheapest model that clears all of them.

**Practical (80 min)** — Write `sentinel/MODEL-MATRIX.md`. Rows: every model you can
actually access (Claude tiers, your local Ollama models, whatever you can serve on your
GPU). Columns: params, context length, $/1M in and out, measured TTFT, measured TPOT,
tool-calling support, structured-output support, where it can run. Fill it with *measured*
numbers from Days 1–8, not vendor claims. Then draft a 20-question SENTINEL-specific mini
benchmark and run every model against it.

**Proof of understanding** — Pick your default model for SENTINEL's triage step and defend
it in three sentences using only numbers from your own matrix. If your justification uses
the phrase "it's the best model," start over.

**Reference** — Your own matrix. Treat every leaderboard as marketing until you have
reproduced it.

---

### Day 11 — **[BUILD]** Local runtime and quantization memory math
**Concept (40 min)** — VRAM required ≈ (parameters × bytes-per-parameter) + KV cache +
activation overhead. KV cache scales with batch size × sequence length × layers × 2 ×
kv-heads × head-dim × bytes. Quantization trades bits-per-parameter for quality. Being able
to do this arithmetic is what lets you answer "can we run this on our hardware, at what
concurrency?" without a two-day spike.

**Practical (80 min)** — Compute by hand, then verify by measurement: VRAM for an 8B model
at FP16, INT8 and 4-bit, at context lengths 4k and 32k, at batch sizes 1 and 8. Run the
quantized variants locally, measure actual memory and tokens/sec, and check your
predictions. Wire the winner into SENTINEL as the local tier of your model router stub.

**Proof of understanding** — State your predicted VRAM and your measured VRAM for the
4-bit 8B model at 32k context. Explain the gap. Then state the largest model you could
serve on your GPU at a concurrency of 16 — that number constrains all of Phase 5.

**Reference** — "LLM.int8()"; "GPTQ: Accurate Post-Training Quantization"; llama.cpp
quantization format documentation.

---

### Day 12 — **[CONSOLIDATE]** The LLM failure taxonomy + publish
**Concept (40 min)** — Consolidate two weeks into a taxonomy you will use as a debugging
checklist for six months: tokenization failures, context-position failures, sampling
variance, structured-output failures, instruction-hierarchy confusion, CoT unfaithfulness,
capability ceiling, and cost/latency blowout. Each one you have now *caused on purpose*.

**Practical (80 min)** — Write `notes/failure-taxonomy.md`: for each failure mode — how it
presents in production, the cheapest diagnostic, the standard mitigation, and a link to
the drill where you reproduced it. Then draft phase deliverable #1: **"The cost & latency
arithmetic every LLM app needs"** — built entirely from your own measurements.

**Proof of understanding** — Hand the taxonomy to an engineer who has not done this phase.
If they can use it to diagnose a failure without asking you a question, it works.

**Reference** — Your `notes/` from days 1–11.

---

## Phase 0 exit checklist

- [ ] `costs.jsonl` has been logging every model call since Day 1
- [ ] You have your own lost-in-the-middle curve, for your own models
- [ ] You can compute cost and p95 latency for a proposed agent design in under 2 minutes
- [ ] `sentinel/SPEC.md` exists with target numbers for all eight success metrics
- [ ] `sentinel/MODEL-MATRIX.md` is filled with measured, not claimed, numbers
- [ ] You know the largest model you can serve at concurrency 16 on your own GPU
- [ ] Phase deliverable #1 is drafted

**Next:** [Phase 1 — Agent Primitives](phase-01-agent-primitives.md)

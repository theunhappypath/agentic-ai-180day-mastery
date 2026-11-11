# Phase 5 — Serving, Inference & Cost Engineering
**Days 121–144 · 4 weeks**

You have already migrated a platform to self-hosted models on your own GPUs, so parts of
this will be familiar. The goal is to convert that operational experience into *first-
principles* understanding — to move from "we tuned it until throughput improved" to
"throughput is bounded by X because of Y, and here is the arithmetic."

The phase's real output is an economic argument you can defend in a room with a CFO: what
this costs, why, on which hardware, and where the breakeven against API pricing actually
sits.

**Phase deliverable:** *On-prem vs API: the breakeven math.*
**Capstone milestone:** SENTINEL v0.5 — cascade routing across local, self-hosted and
frontier tiers with measured $/incident and an enforced latency SLO.

---

## Week 21 — Inference mechanics and the serving stack

### Day 121 — Prefill and decode, properly this time
**Concept (40 min)** — Day 2 gave you the intuition; now derive it. Prefill is a
matrix-matrix operation over the whole prompt — compute-bound, high arithmetic intensity,
excellent GPU utilisation. Decode is matrix-vector, one token at a time — memory-bandwidth-
bound, terrible arithmetic intensity, and the reason a GPU can be at 100% "utilisation"
while doing very little useful FLOP work. Almost every serving optimisation is an attempt to
make decode look more like prefill.

**Practical (80 min)** — Instrument a local model to separate prefill and decode time
precisely. Compute achieved FLOPs during prefill and achieved memory bandwidth during
decode; compare each against your GPU's spec sheet. Calculate the arithmetic intensity of
each phase.

**Proof of understanding** — State your prefill compute utilisation and decode bandwidth
utilisation as percentages of theoretical peak. Then explain, from those numbers, why batching
helps decode enormously and prefill barely at all.

**Reference** — "Efficiently Scaling Transformer Inference"; roofline model analysis.

---

### Day 122 — KV cache memory math and the concurrency ceiling
**Concept (40 min)** — KV cache size per sequence = 2 × layers × kv_heads × head_dim ×
seq_len × bytes_per_element. Multiply by concurrent sequences. This number — not model
weights — is what usually caps concurrency, and it is why long-context serving is so much
more expensive than the token price suggests. Grouped-query attention exists specifically to
shrink it.

**Practical (80 min)** — Compute KV cache size by hand for your chosen model at sequence
lengths {4k, 32k, 128k}. Derive maximum concurrent sequences given your VRAM after weights.
Then verify empirically by increasing concurrency until you OOM.

**Proof of understanding** — Report predicted versus actual maximum concurrency, and explain
the gap (fragmentation, activation memory, framework overhead). Then state SENTINEL's real
concurrency ceiling on your hardware — a number you will use for the rest of the phase.

**Reference** — "GQA: Training Generalized Multi-Query Transformer Models"; the vLLM paper.

---

### Day 123 — Continuous batching and PagedAttention
**Concept (40 min)** — Static batching wastes enormous capacity: the batch runs until the
longest sequence finishes, so short requests hold slots idle. Continuous batching admits new
requests as slots free, at every decode step. PagedAttention manages KV cache in
fixed-size blocks like virtual memory pages, eliminating the fragmentation that forced
conservative pre-allocation. Together these are the single largest throughput improvement in
modern serving.

**Practical (80 min)** — Benchmark the same model with naive batching versus vLLM's
continuous batching under a realistic mixed workload — varied prompt lengths and output
lengths matching SENTINEL's actual distribution, not uniform synthetic requests.

**Proof of understanding** — Report the throughput multiple continuous batching gives you on
*your* workload distribution. Then explain why the multiple is larger when output lengths are
highly variable — this is the mechanism, and SENTINEL's workload is exactly that.

**Reference** — "Efficient Memory Management for Large Language Model Serving with
PagedAttention"; "Orca: A Distributed Serving System for Transformer-Based Generative
Models."

---

### Day 124 — Serving stacks compared
**Concept (40 min)** — **vLLM** — high throughput, broad model support, the default choice.
**SGLang** — strong at structured generation and prefix-heavy workloads via RadixAttention.
**TGI** — solid production ergonomics. **llama.cpp** — CPU and Apple Silicon, quantization
formats, the right tool for local. **TensorRT-LLM** — maximum performance on NVIDIA, at the
cost of a compilation step and rigidity. The choice follows your workload shape, not
benchmarks.

**Practical (80 min)** — Characterise SENTINEL's workload precisely from your OTel data:
prompt length distribution, output length distribution, prefix sharing rate, concurrency
profile, structured output fraction. Then map that to a serving stack choice with reasoning.

**Proof of understanding** — SENTINEL has a high prefix-sharing rate (same system prompt and
tool definitions on every call). State what that implies about RadixAttention-style prefix
caching, and quantify the potential saving from your prompt length distribution.

**Reference** — "SGLang: Efficient Execution of Structured Language Model Programs"; vLLM
and TGI documentation.

---

### Day 125 — **[BUILD]** Stand up vLLM and benchmark properly
**Concept (40 min)** — Benchmarking serving is easy to do badly. Uniform synthetic requests
produce numbers that do not survive contact with real traffic. Use your measured
distribution, warm up before measuring, and report percentiles rather than means.

**Practical (80 min)** — Deploy vLLM on your GPU serving your chosen model. Build a load
generator that replays SENTINEL's real request distribution. Sweep concurrency from 1 to your
Day 122 ceiling, recording throughput (tokens/sec), TTFT p50/p95/p99, TPOT, and GPU memory.

**Proof of understanding** — Plot throughput and p95 TTFT against concurrency, and identify
the knee — the point where adding concurrency raises latency faster than it raises throughput.
That knee is your operating point. State it.

**Reference** — vLLM benchmarking documentation; your Day 84 latency breakdown.

---

### Day 126 — **[CONSOLIDATE]** The serving capacity model
**Concept (40 min)** — Turn the week into a model that answers, without a new experiment:
"how many incidents per hour can this GPU handle at p95 under 90 seconds?"

**Practical (80 min)** — Write `sentinel/serving/CAPACITY.md`: the arithmetic from weights,
KV cache, batching behaviour and your measured curves, to a capacity number. Validate it by
predicting the result of a load test you have not run, then running it. Spaced review: Days
2 and 122.

**Proof of understanding** — Your prediction lands within 20% of the measured result. If it
does not, your model is missing a term — find it. This capacity model is what makes you
useful in a design review.

**Reference** — Your Day 125 curves.

---

## Week 22 — Quantization and decode optimisation

### Day 127 — Quantization formats
**Concept (40 min)** — Reducing bits per parameter cuts memory and increases effective
bandwidth, which directly raises decode throughput. **GPTQ** and **AWQ** are post-training
methods with different calibration approaches; **FP8** is hardware-native on recent NVIDIA
and nearly lossless; **GGUF** k-quants target CPU and Apple Silicon. Quality loss is highly
non-uniform across tasks — it hits structured output, long-context reasoning and instruction
following hardest, which are exactly what agents depend on.

**Practical (80 min)** — Quantize your model to three levels. Measure for each: VRAM,
throughput at your Day 125 operating point, and TTFT. Do not measure quality yet — that is
tomorrow, deliberately separated so you form your speed expectations first.

**Proof of understanding** — Report the memory-to-throughput relationship. Throughput gain
should track the bandwidth reduction closely — if it does not, you are compute-bound
somewhere and should say where.

**Reference** — "GPTQ: Accurate Post-Training Quantization for Generative Pre-trained
Transformers"; "AWQ: Activation-aware Weight Quantization."

---

### Day 128 — Measuring quantization quality loss on your own evals
**Concept (40 min)** — Published quantization benchmarks measure perplexity or MMLU. Neither
predicts whether a quantized model can still emit valid tool-call JSON at step 9 of an
investigation. Agentic workloads are unusually sensitive to quantization because errors
compound across steps — a 2% per-step degradation is a 17% degradation over 9 steps.

**Practical (80 min)** — Run your full Phase 4 replay suite against each quantization level.
Measure everything: root-cause accuracy, tool-call validity rate, trajectory quality,
faithfulness, and false confidence rate. Use the paired comparison from Day 109.

**Proof of understanding** — Report accuracy against quantization level, and separately
report **tool-call validity rate** — it usually degrades faster than answer quality. Name the
lowest quantization level that stays within your minimum detectable effect of full precision.
That is your answer, and it is workload-specific.

**Reference** — Your Day 101 replay suite; Day 109 statistical methodology.

---

### Day 129 — Speculative decoding
**Concept (40 min)** — A small draft model proposes k tokens; the large model verifies them in
a single forward pass, accepting the longest correct prefix. Because decode is
bandwidth-bound, verifying k tokens costs barely more than generating one — so acceptance rate
translates almost directly into speedup. It works best when output is predictable, which
structured output and code notably are.

**Practical (80 min)** — Set up speculative decoding with a small draft model. Measure
acceptance rate and end-to-end speedup separately across three SENTINEL output types:
free-form reasoning, structured JSON tool calls, and the final report. Compare acceptance
rates.

**Proof of understanding** — Report acceptance rate per output type. Structured output should
show the highest rate. Explain the mechanism, and state the overall speedup weighted by
SENTINEL's actual output mix.

**Reference** — "Fast Inference from Transformers via Speculative Decoding"; "Accelerating
Large Language Model Decoding with Speculative Sampling."

---

### Day 130 — Prefix caching and chunked prefill
**Concept (40 min)** — **Prefix caching** reuses computed KV state across requests sharing a
prompt prefix — enormous for agents, where the system prompt and tool definitions are
identical on every call and the conversation itself is an ever-growing shared prefix within
one investigation. **Chunked prefill** splits long prefills into pieces interleaved with
decode steps, so one long prompt does not stall every other request — a p99 fix.

**Practical (80 min)** — Enable both. Measure prefix cache hit rate across a full SENTINEL
investigation, and TTFT with and without. Then measure p99 TTFT under mixed load with and
without chunked prefill.

**Proof of understanding** — Report your prefix cache hit rate within an investigation. It
should be high, because each agent step re-sends the entire prior conversation. Compute what
fraction of your prefill compute that eliminates — this is the largest single serving win
available to agent workloads and most people never enable it.

**Reference** — "SGLang / RadixAttention"; vLLM automatic prefix caching documentation.

---

### Day 131 — **[BUILD]** The quantization and optimisation sweep
**Concept (40 min)** — Combine the week's techniques and find the configuration that
maximises throughput subject to a hard quality constraint.

**Practical (80 min)** — Grid over quantization level × speculative decoding on/off × prefix
caching on/off. For each: throughput, p95 TTFT, and full replay-suite quality. Constrain to
configurations within your minimum detectable effect of full-precision quality, then pick the
fastest.

**Proof of understanding** — Report the chosen configuration and its throughput multiple over
the naive baseline from Day 125, along with the quality delta and its confidence interval.

**Reference** — Your Day 128 quality-versus-quantization curve.

---

### Day 132 — **[CONSOLIDATE]** Serving optimisation review
**Concept (40 min)** — Consolidate what each optimisation bought, so you can advise on this
without re-running experiments.

**Practical (80 min)** — Write `sentinel/serving/OPTIMIZATIONS.md`: each technique, the
mechanism, the measured gain on your workload, the quality cost, and when it does *not* apply.
Spaced review: Days 121 and 128.

**Proof of understanding** — For each technique, state the workload characteristic that
predicts whether it will help. "Prefix caching helps in proportion to prefix sharing rate" is
the level of understanding to reach.

**Reference** — Your sweep results.

---

## Week 23 — Capacity, routing, and caching

### Day 133 — GPU capacity planning and queueing
**Concept (40 min)** — Capacity planning for inference is a queueing problem. Arrival rate,
service rate and the resulting queue length determine latency, and the relationship is
sharply non-linear near saturation — at 90% utilisation, queue wait dominates service time.
This is why "the GPU is only at 85%" and "latency is terrible" are simultaneously true, and
why you must plan to run well below saturation.

**Practical (80 min)** — Model SENTINEL's serving tier as a queue. Measure service time
distribution from your benchmarks, model arrival as bursty (alerts cluster — incidents are
correlated), and compute expected queue wait at utilisations from 50% to 95%. Validate
against a load test.

**Proof of understanding** — State the maximum sustained utilisation at which you still meet
your p95 latency SLO. It will be lower than intuition suggests. Then state how many GPUs
SENTINEL needs at your target incident rate.

**Reference** — Basic queueing theory (M/M/c); "Systems Performance" (Gregg).

---

### Day 134 — Autoscaling, cold starts and multi-model serving
**Concept (40 min)** — GPU autoscaling is painful because cold starts are measured in minutes
— loading tens of gigabytes of weights — while traffic bursts are measured in seconds. The
practical answers are over-provisioning with a warm pool, request queueing with an admission
policy, and multi-model serving so one GPU hosts several models with adapters swapped rather
than whole models reloaded.

**Practical (80 min)** — Measure your actual cold start time from scale-up to first token.
Then design SENTINEL's scaling policy given that number and your Day 133 burst profile.
Implement an admission controller that queues and sheds rather than accepting requests it
cannot serve within SLO.

**Proof of understanding** — Report cold start time and, from it, the warm capacity you must
hold to absorb your worst realistic burst. Load shedding that preserves the SLO for admitted
requests beats accepting everything and missing SLO for all of them — make sure your design
does the former.

**Reference** — Your Day 133 queueing model.

---

### Day 135 — Model routing and cascades
**Concept (40 min)** — Not every step needs your best model. A **cascade** tries a cheap model
first and escalates on low confidence; a **router** classifies difficulty up front and
dispatches. Both depend on a reliable escalation signal — and getting that signal right is the
whole problem, because a bad one either escalates everything (no saving) or escalates nothing
(quality collapse). SENTINEL's steps differ enormously: triage classification is easy,
hypothesis formation is hard.

**Practical (80 min)** — Implement a three-tier cascade — local laptop model → self-hosted
model → frontier API. Design the escalation signal: try token-level confidence, self-reported
confidence, and verifier disagreement, and compare them. Measure cost and quality per routing
policy on the full replay suite.

**Proof of understanding** — Report cost saved and quality lost for each escalation signal.
Then state the cost/quality frontier point you chose and why. If one signal dominates the
others, say which and explain why it works.

**Reference** — "FrugalGPT: How to Use Large Language Models While Reducing Cost and
Improving Performance."

---

### Day 136 — Semantic caching in production
**Concept (40 min)** — Day 64 introduced semantic caching and you were rightly sceptical for
incident response. Revisit it with a sharper eye: it is defensible for *sub-queries* that are
genuinely time-invariant — "what does error code E4021 mean," "what does the billing service
own" — and indefensible for anything reading live state. The design skill is partitioning
your queries into cacheable and non-cacheable classes, not tuning a threshold.

**Practical (80 min)** — Classify SENTINEL's internal queries into time-invariant and
time-sensitive. Implement semantic caching for the former only, with TTLs derived from how
fast the underlying knowledge changes. Measure hit rate and dollars saved on the safe subset.

**Proof of understanding** — Report hit rate and savings on the cacheable subset. Then state
the rule you would give another engineer for deciding cacheability — the rule, not the
threshold, is the transferable artifact.

**Reference** — Your Day 64 false-hit example.

---

### Day 137 — **[BUILD]** The SENTINEL cascade router
**Concept (40 min)** — Integrate routing, cascading and caching into one serving layer with a
single interface the agent code calls, and full observability so you can see which tier served
each request.

**Practical (80 min)** — Build `sentinel/serving/router.py`: per-step model policy, cascade
escalation with your chosen signal, semantic cache for the safe subset, circuit breakers per
tier (from Day 118), and OTel spans tagging the serving tier. Run the full replay suite.

**Proof of understanding** — Report cost per incident for v0.5 versus v0.4, and the tier
distribution — what fraction of calls were served locally, self-hosted, and by the frontier
API. That distribution is the heart of your Phase 5 write-up.

**Reference** — Your Day 112 cost attribution.

---

### Day 138 — **[CONSOLIDATE]** Cost attribution after routing
**Concept (40 min)** — Re-run the Day 112 attribution against the routed system. The cost
structure has changed shape, and the new dominant cost centre is your next target.

**Practical (80 min)** — Full cost and latency attribution on v0.5. Compare the shape against
v0.4. Spaced review: Days 112 and 135.

**Proof of understanding** — Name the new dominant cost centre. After routing, it is often
the frontier-model escalations — a small fraction of calls carrying most of the cost. That
observation is precisely what motivates Phase 6.

**Reference** — Your dashboard.

---

## Week 24 — Latency, economics, and the serving-layer contract

### Day 139 — Latency budgeting
**Concept (40 min)** — A latency budget is allocated top-down: if p95 time to hypothesis must
be 90 seconds, and the investigation has 8 sequential model calls plus retrieval, each
component gets an explicit share. Components that exceed their share must be optimised,
parallelised, or removed. Without an allocated budget you optimise whatever is easiest rather
than whatever matters.

**Practical (80 min)** — Build SENTINEL's latency budget as a table: every component, its
allocation, its measured p50 and p95, and its variance. Identify every component over budget.
Then enforce it in code — components that exceed their allocation trigger the Day 93
degradation ladder.

**Proof of understanding** — Report which components are over budget and by how much. Then
state what fraction of your total budget is spent *waiting* — on rate limits, queueing, and
network — rather than computing. It is usually a lot, and it is the cheapest thing to fix.

**Reference** — Your Day 111 traces.

---

### Day 140 — Tail latency: where p99 actually comes from
**Concept (40 min)** — p99 is a different problem from p50 and rarely has the same cause.
Sources: queueing at high utilisation, one long-context request stalling the batch, a retry
after a transient failure, a cache miss on a normally-cached path, and garbage collection or
paging. Tail latency in a multi-step agent is especially punishing — one slow step in eight
drags the whole investigation, and the probability of hitting at least one slow step compounds
with step count.

**Practical (80 min)** — Isolate your p99 investigations from the traces and categorise the
cause of each. Then compute the compounding effect: given per-step p99, what is the
probability that an 8-step investigation contains at least one p99 step?

**Proof of understanding** — Report that probability. It is uncomfortably high, and it is the
argument for hedged requests, aggressive per-step timeouts, and fewer steps. State which
mitigation you chose.

**Reference** — "The Tail at Scale" (Dean & Barroso).

---

### Day 141 — Cost engineering and the on-prem breakeven
**Concept (40 min)** — The full model: API cost is purely marginal per token. On-prem cost is
capital amortisation plus power plus cooling plus the engineering time to run it, divided by
tokens actually served — which means **utilisation dominates the economics**. A GPU at 15%
utilisation is dramatically more expensive per token than an API. Most on-prem
cost-saving claims quietly assume utilisation nobody achieves.

**Practical (80 min)** — Build the full model in a spreadsheet: your GPU's capital cost
amortised over 3 years, power at your electricity rate, an estimate of operational
engineering time, divided by tokens served at utilisation levels from 10% to 80%. Plot
$/1M tokens against utilisation, with the API price as a horizontal line.

**Proof of understanding** — State the utilisation at which your on-prem serving beats the
API price for an equivalent-capability model. Then state your *actual* current utilisation.
If it is below breakeven, say so plainly — this is the number your bio's cost claim should
rest on, and it is far more credible with the honest version attached.

**Reference** — Your `costs.jsonl`; your GPU's specifications and your electricity rate.

---

### Day 142 — Guided decoding at the serving layer
**Concept (40 min)** — Day 8 covered constrained decoding conceptually; here it is an
infrastructure decision. Serving-layer guided decoding (xgrammar, Outlines integration)
compiles a schema into a token mask applied during generation. It guarantees valid structure,
adds compilation overhead on first use per schema, and can be cached. For an agent making
thousands of tool calls, guaranteed-valid JSON removes an entire class of retry cost.

**Practical (80 min)** — Enable guided decoding in your serving stack for SENTINEL's tool
call schemas. Measure: tool-call validity rate, added latency, schema compilation overhead
and its cache hit rate. Compare against your Day 21 repair-loop cost.

**Proof of understanding** — Report the total cost of repair loops in v0.4 versus the cost of
guided decoding in v0.5. Guided decoding usually wins outright — but confirm it, and check
whether the Day 8 quality caveat (constrained output can suppress useful reasoning) shows up
in your replay suite.

**Reference** — "XGrammar: Flexible and Efficient Structured Generation"; your Day 8 results.

---

### Day 143 — **[BUILD]** SENTINEL v0.5
**Concept (40 min)** — Integration. v0.5 = optimised self-hosted serving + cascade routing +
prefix and semantic caching + guided decoding + enforced latency budget + capacity model.

**Practical (80 min)** — Assemble, run the full replay suite, load test at your target
incident rate, tag `v0.5`, update the changelog with cost per incident, tier distribution, and
p95 latency.

**Proof of understanding** — v0.5 versus v0.4: cost per incident and p95 latency, with the
quality delta and its confidence interval. The target is materially lower cost at
statistically indistinguishable quality. Report honestly if you traded quality for cost.

**Reference** — `sentinel/CHANGELOG.md`.

---

### Day 144 — **[CONSOLIDATE]** Phase 5 review + publish
**Concept (40 min)** — The thesis: LLM serving economics are dominated by utilisation and
by memory bandwidth, most cost-optimisation advice ignores both, and the on-prem breakeven is
a utilisation question rather than a token-price question.

**Practical (80 min)** — Draft deliverable #6: **"On-prem vs API: the breakeven math."** Lead
with the Day 141 utilisation curve. Include the Day 130 prefix cache saving, the Day 128
quantization quality cliff, and the Day 137 tier distribution. Spaced review: Days 122 and 141.

**Proof of understanding** — A reader can plug in their own GPU cost, electricity rate and
utilisation and get their own breakeven. Give them the model, not just your answer.

**Reference** — Your `notes/` from Days 121–143.

---

## Phase 5 exit checklist

- [ ] You can derive KV cache size and concurrency ceiling from first principles
- [ ] vLLM benchmarked on your real workload distribution; operating point identified
- [ ] A capacity model that predicts load-test results within 20%
- [ ] Quantization quality measured on your own evals, including tool-call validity
- [ ] Speculative decoding acceptance rate measured per output type
- [ ] Prefix caching enabled; hit rate and prefill savings quantified
- [ ] Queueing model giving maximum utilisation at your latency SLO
- [ ] Three-tier cascade with a measured, chosen escalation signal
- [ ] Latency budget allocated per component and enforced in code
- [ ] p99 causes categorised; compounding probability across steps computed
- [ ] On-prem breakeven utilisation computed, and your actual utilisation stated honestly
- [ ] Guided decoding replacing repair loops, with the cost comparison
- [ ] SENTINEL v0.5 tagged
- [ ] Phase deliverable #6 drafted

**Next:** [Phase 6 — Adaptation](phase-06-adaptation.md)

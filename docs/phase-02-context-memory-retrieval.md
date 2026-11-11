# Phase 2 — Context, Memory & Retrieval
**Days 37–66 · 5 weeks**

Day 24 almost certainly told you that most of your agent's failures were retrieval
failures — it never surfaced the evidence it needed. This phase is long because that is
where the accuracy lives, and because "put it in a vector database" is roughly 15% of a
working retrieval system.

The phase opens with evaluation, not with embeddings. That ordering is deliberate and it is
the single most transferable lesson here: **you cannot tune what you cannot measure, and
retrieval quality is exceptionally easy to fool yourself about.**

**Phase deliverable:** *Write the retrieval eval before you tune retrieval.*
**Capstone milestone:** SENTINEL v0.2 — hybrid heterogeneous retrieval, service graph,
memory, caching, all measured.

---

## Week 7 — Evaluation first, then chunking

### Day 37 — Retrieval metrics that mean something
**Concept (40 min)** — Recall@k (did the right document appear in the top k — the metric
that matters most for RAG, because the generator can ignore noise but cannot invent what
was never retrieved), MRR (how high did the first relevant result rank), and nDCG (graded
relevance with position discounting). Also: **context precision** — of what you retrieved,
how much was actually useful — because retrieving 20 chunks to get 2 good ones has a real
cost in tokens and in the Day 4 position effect.

**Practical (80 min)** — Implement all four metrics from scratch in
`sentinel/evals/retrieval_metrics.py`. No libraries — you will trust them more and you will
understand the failure modes. Validate against small hand-computed examples where you know
the answer.

**Proof of understanding** — Construct a retrieval result set where recall@10 is perfect
and MRR is terrible, and explain which failure a RAG system actually suffers from. Then
argue which metric SENTINEL should optimise and why.

**Reference** — "Introduction to Information Retrieval" (Manning et al.), evaluation
chapters.

---

### Day 38 — Building the labelled evaluation set
**Concept (40 min)** — A retrieval eval set is a list of queries, each with the set of
documents that genuinely answer it. Building it is tedious and it is the highest-value work
in the phase. Coverage matters: easy lexical-match queries, paraphrase queries with no
shared vocabulary, multi-hop queries needing two documents, and queries with no good answer
at all — the last category catches systems that always return something confidently.

**Practical (80 min)** — Build 100 labelled queries over your incident corpus. Derive many
from the minimal evidence sets you already wrote — you have ground truth for free. Include
at least 15 queries with *no* correct answer. Store as `sentinel/evals/retrieval_set.json`.

**Proof of understanding** — Report your query-type distribution. Then run your current
naive retrieval against it and record baseline recall@5 and MRR. This baseline is the
number every subsequent day in this phase is fighting.

**Reference** — BEIR benchmark methodology for eval set construction.

---

### Day 39 — Chunking strategies
**Concept (40 min)** — Chunking decides what can ever be retrieved. Fixed-size is simple
and severs meaning mid-sentence. Recursive splitting on structural separators respects
boundaries. Semantic chunking splits on embedding-distance shifts. Overlap trades storage
for boundary safety. There is no universal best — it depends entirely on the document
structure, which is why measuring on *your* corpus beats copying a default.

**Practical (80 min)** — Implement four strategies. Sweep them across your runbook and
documentation corpus at sizes {256, 512, 1024, 2048} tokens with overlaps {0, 10%, 20%}.
Evaluate every configuration against the Day 38 set.

**Proof of understanding** — Report the best and worst configuration by recall@5. The
spread is usually large. Explain the mechanism behind the winner — this teaches you more
than the winner itself.

**Reference** — "Dense Passage Retrieval for Open-Domain Question Answering."

---

### Day 40 — Structure-aware and AST-based chunking
**Concept (40 min)** — Generic chunkers destroy structured content. Code should be chunked
on function and class boundaries with the enclosing context attached. Logs should be chunked
by time window and correlation ID, not by character count. Traces are trees, not text.
Markdown has a heading hierarchy that carries meaning. Structure-aware chunking usually beats
any amount of tuning on a generic chunker.

**Practical (80 min)** — Build an AST-based code chunker using tree-sitter: chunks are
functions/classes, each prefixed with its file path, imports and enclosing class signature.
Build a log chunker keyed on correlation ID and time window. Compare both against generic
chunking on the code and log slices of your eval set.

**Proof of understanding** — Report recall@5 for structure-aware versus generic chunking on
code queries specifically. Then find a query that only the structure-aware chunker gets
right and explain exactly why.

**Reference** — tree-sitter documentation; "CodeSearchNet Challenge."

---

### Day 41 — **[BUILD]** SENTINEL retrieval evaluation harness
**Concept (40 min)** — Make evaluation a one-command operation, or you will stop running it
by Day 50. The harness must be fast enough to run on every change and must report per-query
results, not just aggregates — the aggregate hides the queries you are systematically
failing.

**Practical (80 min)** — Build `sentinel/evals/run_retrieval_eval.py`: takes a retrieval
config, runs all 100 queries, outputs aggregate metrics plus a per-query breakdown, and
writes results to a versioned file so you can diff configurations. Add a regression check
that flags any query that used to pass and now fails.

**Proof of understanding** — Full eval runs in under 60 seconds. If it takes 10 minutes,
you will run it weekly instead of hourly, and you will tune blind.

**Reference** — Your Day 37 metrics implementation.

---

### Day 42 — **[CONSOLIDATE]** What retrieval is failing at
**Concept (40 min)** — Read the per-query failures, not the aggregate. Classify: vocabulary
mismatch (query and document share no terms), granularity mismatch (the answer spans two
chunks), specificity failure (retrieved the topically right document but the wrong section),
and the no-answer queries where the system returned something confidently anyway.

**Practical (80 min)** — Label every failing query with a class. Tally. Write
`notes/day-042.md`. Spaced review: Days 7 and 33.

**Proof of understanding** — Name your dominant failure class and predict which of the next
three weeks will fix it. Check your prediction on Day 66.

**Reference** — Your per-query eval output.

---

## Week 8 — Indexes: dense, sparse, and both

### Day 43 — Embedding model selection
**Concept (40 min)** — Embedding models differ on dimensionality (storage and speed),
max sequence length (which caps chunk size), domain fit (a general model is weak on code and
on log syntax), symmetric versus asymmetric training (query-document models expect the
query and document to look different, which matters enormously), and whether they expect an
instruction prefix. Leaderboard position is a weak predictor of performance on your corpus.

**Practical (80 min)** — Benchmark four embedding models on your eval set: a general-purpose
hosted model, a small local model, a code-specialised model, and a large open model served
locally. Measure recall@5, embedding latency, index size and cost per million tokens.

**Proof of understanding** — Report the table. Then answer the real question: is the best
model worth its cost and latency over the second-best, for SENTINEL's specific budget? Cite
Day 6's calculator.

**Reference** — MTEB benchmark methodology; "Text and Code Embeddings by Contrastive
Pre-Training."

---

### Day 44 — Vector index internals: HNSW and IVF
**Concept (40 min)** — Approximate nearest neighbour search trades recall for speed via
explicit knobs. HNSW builds a navigable multi-layer graph — `M` (connectivity) and
`ef_construction` set index quality, `ef_search` sets the query-time recall/latency
tradeoff. IVF partitions the space into clusters and probes `nprobe` of them. Defaults are
usually tuned for benchmark-scale data and are frequently wrong for a small, high-value
corpus like yours.

**Practical (80 min)** — Build an HNSW index over your corpus. Sweep `ef_search` across a
wide range and plot recall against query latency. Do the same for `M`. Then compare against
exact brute-force search — at your corpus size, brute force may well win outright.

**Proof of understanding** — State the corpus size at which ANN starts beating brute force
on your hardware. Many production systems run ANN over 50k vectors where exact search would
be both faster and perfectly accurate. Know which side of that line you are on.

**Reference** — "Efficient and robust approximate nearest neighbor search using Hierarchical
Navigable Small World graphs"; FAISS documentation.

---

### Day 45 — Lexical retrieval: BM25 from scratch
**Concept (40 min)** — BM25 scores by term frequency, inverse document frequency and length
normalisation. It has no notion of semantics — and it beats dense retrieval decisively on
exact identifiers: error codes, stack frames, service names, UUIDs, function names.
Precisely the content that dominates incident response. Dense-only retrieval systems fail
on production telemetry for exactly this reason.

**Practical (80 min)** — Implement BM25 from scratch — tokenization, IDF, the `k1` and `b`
parameters. Index your corpus and evaluate. Then isolate the queries containing exact
identifiers and compare BM25 against dense retrieval on that subset only.

**Proof of understanding** — Report the BM25-versus-dense gap on identifier queries. It will
be dramatic and in BM25's favour. This is the empirical justification for everything in
Day 46.

**Reference** — "The Probabilistic Relevance Framework: BM25 and Beyond."

---

### Day 46 — Hybrid retrieval and reciprocal rank fusion
**Concept (40 min)** — Combining lexical and dense retrieval beats either alone because
their failure modes are uncorrelated. Score-based fusion requires normalising incompatible
score scales and is fragile. **Reciprocal rank fusion** combines by rank instead —
score = Σ 1/(k + rank_i) — needs no normalisation, is nearly parameter-free, and is
remarkably hard to beat.

**Practical (80 min)** — Implement RRF over your BM25 and dense retrievers. Sweep `k`. Also
implement weighted score fusion with normalisation, so you can compare. Evaluate both, and
break results down by query type.

**Proof of understanding** — Report hybrid versus each component alone, overall and per
query type. Identify any query type where hybrid is *worse* than the best single retriever —
this happens, and understanding when is what separates you from someone following a tutorial.

**Reference** — "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning
Methods."

---

### Day 47 — **[BUILD]** Hybrid index over the SENTINEL corpus
**Concept (40 min)** — Production shape: separate indexes per content type (logs, traces,
code, runbooks) with per-type chunking and per-type retrieval weighting, fused at query
time. One index over everything is simpler and materially worse.

**Practical (80 min)** — Build four indexes with type-appropriate chunkers and embedding
models. Implement a fused retrieval interface that queries all four and merges with RRF.
Wire it into SENTINEL's tools. Re-run the incident corpus end to end.

**Proof of understanding** — Report root-cause accuracy@1 and evidence recall against
v0.1. Evidence recall should move substantially — that was the point of the whole week.

**Reference** — Your Day 35 v0.1 metrics.

---

### Day 48 — **[CONSOLIDATE]** Retrieval cost accounting
**Concept (40 min)** — Retrieval has real costs people forget to count: embedding the corpus
(one-time plus re-index), embedding every query (per-request), index memory, and the tokens
that retrieved context consumes in every downstream call. That last one usually dominates.

**Practical (80 min)** — Compute total retrieval cost per investigation: query embedding
cost + the token cost of retrieved context across all agent steps. Add it to `costs.jsonl`
as a tagged category. Spaced review: Days 6 and 19.

**Proof of understanding** — State what fraction of SENTINEL's per-incident cost is
retrieved context. If it is above 50%, Day 49's reranking is about to pay for itself by
letting you retrieve fewer, better chunks.

**Reference** — Your `costs.jsonl`.

---

## Week 9 — Making retrieval smarter

### Day 49 — Reranking with cross-encoders
**Concept (40 min)** — Bi-encoders embed query and document separately, so they scale but
never compare the two directly. Cross-encoders process the pair jointly and are far more
accurate — and far too slow to run over a corpus. The standard architecture: retrieve 50
cheaply, rerank to the top 5 expensively. This is usually the largest single quality win
available in a RAG system.

**Practical (80 min)** — Add a cross-encoder reranker. Sweep the retrieve-then-rerank
depth: retrieve {20, 50, 100} → rerank to 5. Measure recall@5, nDCG, added latency and added
cost at each depth. Plot quality against latency.

**Proof of understanding** — Find the knee in your quality/latency curve and state the
retrieval depth you chose. Then check it against SENTINEL's p95 latency budget from
`SPEC.md` — the best quality point may be outside your budget, and choosing correctly under
that constraint is the actual skill.

**Reference** — "Multi-Stage Document Ranking with BERT"; "Passage Re-ranking with BERT."

---

### Day 50 — Query transformation
**Concept (40 min)** — The user's query is often a poor search key. **HyDE** generates a
hypothetical answer and embeds *that*, because answers look more like documents than
questions do. **Multi-query** generates several paraphrases and unions the results.
**Decomposition** splits a multi-hop question into sub-questions. Each costs a model call —
so each must be justified against measured lift, not adopted because it sounds clever.

**Practical (80 min)** — Implement all three. Evaluate each against your set, broken down by
query type. Track added latency and cost per query.

**Proof of understanding** — Report lift per technique per query type, alongside cost. At
least one technique will not justify its cost for SENTINEL. Name it and cut it — that
decision is the deliverable, not the implementation.

**Reference** — "Precise Zero-Shot Dense Retrieval without Relevance Labels" (HyDE);
"Least-to-Most Prompting."

---

### Day 51 — Query routing and retrieval planning
**Concept (40 min)** — Not every query should hit every index. "What deployed at 14:32?"
needs deploy history, not the runbook corpus. A router classifies the query and dispatches
to the right index with the right strategy — saving both latency and the token cost of
irrelevant context, while improving precision.

**Practical (80 min)** — Build a query router. Try three implementations: keyword rules, an
embedding classifier over labelled examples, and a small-model classifier. Compare accuracy,
latency and cost. Measure end-to-end retrieval quality with routing versus fan-out-to-all.

**Proof of understanding** — Report the cost and latency saved by routing, and the accuracy
change. If routing costs accuracy, quantify the trade and decide explicitly. Note which
router implementation won — it is often the rules.

**Reference** — Your Day 43 model matrix, for router model selection.

---

### Day 52 — Agentic RAG: retrieval as a tool the agent controls
**Concept (40 min)** — Static RAG retrieves once and generates. Agentic RAG gives the agent
retrieval as a tool it invokes deliberately, inspects, and re-invokes with refined queries.
This matches investigation perfectly — you look at logs, that points at a service, so you
fetch that service's traces. The risks are unbounded retrieval loops and context bloat.

**Practical (80 min)** — Convert SENTINEL's retrieval into an agent-controlled tool with an
explicit retrieval budget (max 8 calls per investigation). Add a "what have I already
retrieved" summary to state so the agent doesn't re-fetch. Compare against single-shot
retrieval on the corpus.

**Proof of understanding** — Report accuracy and cost for agentic versus single-shot
retrieval. Then report the distribution of retrieval calls per investigation. If it is
bimodal — some investigations use 1, some hit the cap of 8 — the cap is binding and you need
to know whether those are hard cases or runaway loops.

**Reference** — "Self-RAG: Learning to Retrieve, Generate, and Critique."

---

### Day 53 — **[BUILD]** Agentic retrieval in SENTINEL
**Concept (40 min)** — Integrate the week: reranking, the surviving query transformations,
routing, and the agent-controlled retrieval loop, all inside the retrieval budget.

**Practical (80 min)** — Wire it together and run the corpus. Then run an ablation — turn
off each component individually and measure the drop.

**Proof of understanding** — Produce the ablation table. Any component whose removal costs
less than 1 point of accuracy while adding latency should be cut. Cut it.

**Reference** — Your Day 41 eval harness.

---

### Day 54 — **[CONSOLIDATE]** Retrieval architecture review
**Concept (40 min)** — Write down the architecture you arrived at and, critically, why each
piece is there. In three months you will not remember why the reranker retrieves 50 instead
of 100, and you will change it and quietly lose accuracy.

**Practical (80 min)** — Write `sentinel/retrieval/ARCHITECTURE.md` — every component, its
configuration, the measurement that justifies it, and what you tried that lost. Spaced
review: Days 37 and 45.

**Proof of understanding** — Every configuration constant in the file cites a specific
measurement. Any constant you cannot justify is a constant you copied from somewhere.

**Reference** — Your ablation table.

---

## Week 10 — Structured and heterogeneous retrieval

### Day 55 — Knowledge graphs for retrieval
**Concept (40 min)** — Some questions are inherently relational and no amount of embedding
similarity answers them: "which services depend on auth?", "who owns billing?", "what is
downstream of the thing that changed?" A graph answers those exactly and cheaply. In
incident response, the service dependency graph is the single most useful non-text structure
you have, because failures propagate along it.

**Practical (80 min)** — Build the service graph for your toy system: services as nodes,
dependencies as directed edges, with owner, runbook link and deploy cadence as attributes.
Expose graph queries as an agent tool — dependents_of, dependencies_of, path_between,
blast_radius.

**Proof of understanding** — Find an incident in your corpus that the agent solves with the
graph and could not solve without it. Cascading-failure incidents are where this earns its
place.

**Reference** — "Knowledge Graphs" (Hogan et al.); Neo4j or NetworkX documentation.

---

### Day 56 — GraphRAG and global questions
**Concept (40 min)** — Standard RAG answers local questions — questions whose answer lives
in a few chunks. It fails on global questions: "what are the recurring themes across our
last 50 incidents?" GraphRAG builds an entity graph over the corpus, detects communities,
summarizes each, and answers global questions from those summaries. Expensive to build, and
occasionally the only thing that works.

**Practical (80 min)** — Build a small entity graph over your incident corpus — services,
error types, root-cause categories, engineers. Detect communities and summarize them.
Answer three global questions ("what fails most often after a deploy?") that flat RAG
cannot.

**Proof of understanding** — Show a question flat RAG answers badly and GraphRAG answers
well. Then state the build cost in dollars and decide whether SENTINEL should carry it —
the honest answer for a 150-incident corpus may well be no.

**Reference** — "From Local to Global: A Graph RAG Approach to Query-Focused
Summarization."

---

### Day 57 — Text-to-SQL over telemetry
**Concept (40 min)** — Metrics are numbers in tables, and semantic search over numbers is
nonsense. The right tool is text-to-SQL: schema in context, model writes a query, you
execute it against a read-only connection with a row limit and a timeout. The failure modes
are specific — hallucinated columns, wrong joins, and queries that are valid SQL but answer
a different question than was asked.

**Practical (80 min)** — Build a metrics query tool over your telemetry store. Include the
schema plus a few example rows in the prompt. Add validation: parse the SQL, verify every
referenced table and column exists, enforce a read-only connection, a `LIMIT`, and a
timeout. Test on 25 metric questions.

**Proof of understanding** — Report execution success rate versus *semantic* correctness
rate. The gap between them is the dangerous number — a query that runs and returns the wrong
answer is worse than one that errors, because the agent believes it.

**Reference** — "Spider: A Large-Scale Human-Labeled Dataset for Text-to-SQL"; your Day 8
constrained decoding work.

---

### Day 58 — Heterogeneous retrieval and cross-source fusion
**Concept (40 min)** — SENTINEL now retrieves across five modalities — text (runbooks),
code (AST-chunked), semi-structured (logs), tree-structured (traces), tabular (metrics) and
graph (dependencies). Fusing them is not just merging ranked lists: results have
incomparable units, different token costs, and different evidentiary weight. A single trace
span can be worth more than 50 log lines.

**Practical (80 min)** — Build the fusion layer: per-source retrieval, per-source budget in
tokens, and an evidence-weighting scheme. Present retrieved evidence to the agent grouped by
source with provenance attached. Measure whether grouping-with-provenance beats a flat
merged list.

**Proof of understanding** — Report the accuracy difference between grouped and flat
presentation. Then check the Day 4 position effect: does putting the highest-weight
evidence last change the result? Test it rather than guessing.

**Reference** — Your Day 4 lost-in-the-middle curve.

---

### Day 59 — **[BUILD]** Service graph and telemetry tools in SENTINEL
**Concept (40 min)** — Integration day for structured retrieval — graph queries plus the
SQL tool joined to the text retrieval stack.

**Practical (80 min)** — Wire both into SENTINEL's toolset via MCP. Re-run the corpus.
Pay attention to whether the agent actually *uses* the graph tool — a tool the model never
calls is a schema problem (Day 14), not a capability problem.

**Proof of understanding** — Report per-tool call frequency across 20 investigations. Any
tool called in under 10% of investigations either has a bad description or should not exist.
Decide which.

**Reference** — Your Day 14 schema variant experiment.

---

### Day 60 — **[CONSOLIDATE]** Evidence quality over evidence quantity
**Concept (40 min)** — More retrieved context is not better context. It costs tokens, it
dilutes attention, and it increases the chance the agent latches onto something irrelevant
but vivid. Precision now matters as much as recall.

**Practical (80 min)** — Measure context precision: of the evidence presented to the agent,
what fraction appears in the ground-truth minimal evidence set? Then deliberately halve the
evidence budget and re-measure accuracy. Spaced review: Days 33 and 49.

**Proof of understanding** — Report accuracy at full versus half evidence budget. If halving
it barely hurts, you have been paying for noise since Day 47. This is a common and expensive
finding.

**Reference** — Your ground-truth minimal evidence sets.

---

## Week 11 — Memory, long context, and caching

### Day 61 — Long context versus RAG
**Concept (40 min)** — With large context windows, "just put everything in the prompt" is
sometimes genuinely correct — no index, no chunking, no retrieval failures. It is also
sometimes 40× more expensive per call and slower, and it runs straight into Day 4's
position degradation. The decision is arithmetic: corpus size, query frequency, cache hit
rate, latency budget.

**Practical (80 min)** — For one incident, implement both: full-context (stuff every log,
trace and diff into one prompt) versus your retrieval pipeline. Measure accuracy, cost, TTFT
and total latency. Then compute the corpus size at which they cross over.

**Proof of understanding** — State the crossover point in tokens for your budget, and the
decision rule you would give another engineer: "below N tokens per incident with fewer than
M queries, skip retrieval entirely." Getting to a *rule* is the goal.

**Reference** — Your Day 6 budget calculator and Day 4 degradation curve.

---

### Day 62 — Memory architectures
**Concept (40 min)** — Three kinds, with different lifetimes and storage. **Working memory**
is the current context — ephemeral. **Episodic memory** is specific past events ("we saw
this exact error in INC-0031") — retrievable, high value, grows without bound. **Semantic
memory** is distilled general knowledge ("the billing service has a connection pool that
saturates under retry storms") — small, extremely high value, hard to build correctly.

**Practical (80 min)** — Implement episodic memory for SENTINEL: index every completed
investigation — symptoms, evidence, root cause, fix — and retrieve similar past incidents at
the start of a new one. Measure accuracy with and without the episodic lookup, using
leave-one-out so the current incident cannot retrieve itself.

**Proof of understanding** — Report the accuracy lift from episodic memory. Then find the
failure case: an incident where a *similar-looking but differently-caused* past incident led
the agent astray. Episodic memory creates confident wrong answers, which is your
false-confidence metric getting worse.

**Reference** — "Generative Agents: Interactive Simulacra of Human Behavior" (memory stream
design); "MemGPT: Towards LLMs as Operating Systems."

---

### Day 63 — Memory writeback, consolidation and forgetting
**Concept (40 min)** — Memory that only grows becomes a retrieval problem of its own. Real
systems need: a writeback policy (what is worth remembering — not every investigation),
consolidation (turning ten similar episodes into one semantic fact), and forgetting
(decay, or explicit invalidation when a service is rewritten and old knowledge becomes
actively wrong). Stale memory is worse than no memory.

**Practical (80 min)** — Implement a writeback policy gated on investigation confidence and
human confirmation. Implement consolidation: after N similar incidents, generate a semantic
memory entry and demote the episodes. Implement invalidation keyed on service version.

**Proof of understanding** — Construct the stale-memory scenario deliberately: write a
semantic memory, change the underlying system so it is false, and show your agent confidently
applying outdated knowledge. Then show your invalidation catching it.

**Reference** — Your Day 62 memory implementation.

---

### Day 64 — Caching: prompt cache, semantic cache, and invalidation
**Concept (40 min)** — Two very different mechanisms. **Prompt caching** caches the model's
internal state for a stable prompt prefix — large cost and latency savings, requires you to
structure prompts prefix-stable (static system prompt and tool definitions first, volatile
content last) and has a TTL. **Semantic caching** returns a stored response for a
sufficiently similar query — far riskier, because "similar enough" is a threshold you will
get wrong, and a stale cached answer during an outage is actively harmful.

**Practical (80 min)** — Restructure SENTINEL's prompts to be prefix-stable and enable
prompt caching. Measure hit rate and dollars saved across a corpus run. Then implement
semantic caching with a similarity threshold, and deliberately find a query pair that is
above threshold but should *not* share an answer.

**Proof of understanding** — Report prompt-cache hit rate and cost saved. Then present your
semantic-cache false-hit example and make an explicit decision about whether SENTINEL should
use semantic caching at all. For incident response the defensible answer is probably no —
but it must be your reasoned answer.

**Reference** — Anthropic prompt caching documentation.

---

### Day 65 — **[BUILD]** SENTINEL v0.2
**Concept (40 min)** — Integration. v0.2 = heterogeneous hybrid retrieval + reranking +
routing + agentic retrieval loop + service graph + telemetry SQL + episodic and semantic
memory + prompt caching, all inside measured budgets.

**Practical (80 min)** — Assemble, run the full corpus, tag `v0.2`, update the changelog
with all eight success metrics.

**Proof of understanding** — v0.1 versus v0.2 across every metric, including cost per
incident. If accuracy rose and cost rose more than 3×, you have a Phase 5 problem — note it
now, because Phase 5 will be measured against exactly this.

**Reference** — `sentinel/CHANGELOG.md`.

---

### Day 66 — **[CONSOLIDATE]** Phase 2 review + publish
**Concept (40 min)** — The thesis: retrieval quality is measurable, most retrieval systems
are never measured, and the measurement is what produces the gains — not the technique
selection.

**Practical (80 min)** — Draft deliverable #3: **"Write the retrieval eval before you tune
retrieval."** Lead with the Day 38 baseline and the v0.2 number, and show the ablation table
that says which techniques actually earned their place. Check your Day 42 prediction. Spaced
review: Days 38 and 58.

**Proof of understanding** — Your write-up includes at least one technique that is widely
recommended and did not work on your corpus. Those are the most useful posts in this field
and almost nobody writes them.

**Reference** — Your `notes/` from Days 37–65.

---

## Phase 2 exit checklist

- [ ] 100-query labelled retrieval eval set, including no-answer queries
- [ ] Eval runs end to end in under 60 seconds
- [ ] BM25 implemented from scratch; you can state its advantage over dense on identifiers
- [ ] Four content-type-specific indexes fused with RRF
- [ ] An ablation table justifying every retrieval component
- [ ] Service dependency graph and validated text-to-SQL tools
- [ ] Episodic and semantic memory with writeback, consolidation and invalidation
- [ ] Prompt caching enabled, hit rate and savings measured
- [ ] SENTINEL v0.2 tagged with full metrics
- [ ] Phase deliverable #3 drafted

**Next:** [Phase 3 — Multi-Agent Orchestration](phase-03-orchestration.md)

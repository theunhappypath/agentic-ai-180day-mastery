# Phase 6 — Adaptation: Fine-tuning, Distillation & Routing
**Days 145–156 · 2 weeks**

The shortest phase, deliberately. Fine-tuning is the most over-reached-for tool in applied
AI: it is expensive, it creates a model you now have to version, evaluate and serve, and it
is very frequently the wrong answer to a problem that better tools or better retrieval
would have solved.

You are doing it anyway — because Day 138 told you that a small fraction of frontier
escalations carries most of your cost, and that is exactly the shape of problem where a
distilled small model earns its keep.

**Phase deliverable:** *Distilling your agent's hot path.*
**Capstone milestone:** SENTINEL v0.6 — distilled model serving the high-volume triage hop,
with the cost and quality delta measured.

---

## Week 25 — When, and how, to adapt

### Day 145 — When *not* to fine-tune
**Concept (40 min)** — The decision tree, in order: better prompting, better tool design,
better retrieval, a bigger model, few-shot examples, and only then fine-tuning. Fine-tuning
is the right answer for narrow, high-volume, well-specified tasks where you have or can
generate good data, and where a small model needs to acquire a *behaviour* rather than
*knowledge*. It is the wrong answer for injecting facts (retrieval does that better and stays
current), for broad capability, and for anything where the task specification is still moving.

**Practical (80 min)** — Audit every SENTINEL step against the tree. For each, write down
what you would try before fine-tuning and whether you have actually tried it. Identify the one
or two steps that genuinely qualify — high call volume, narrow task, existing training data
from your traces.

**Proof of understanding** — Name the steps you ruled *out* and why. If you concluded that
every step needs fine-tuning, you have skipped the exercise. The triage classification hop is
the strong candidate: highest volume, narrowest task, and you have thousands of labelled
examples from your own corpus runs.

**Reference** — Your Day 138 cost attribution.

---

### Day 146 — Dataset construction and curation
**Concept (40 min)** — Data quality dominates data volume — a thousand carefully curated
examples routinely beat fifty thousand noisy ones. What matters: correctness, diversity across
the input distribution, consistent output formatting, and hard negatives. The most common
failure is training on your own model's outputs without filtering, which bakes in existing
errors and narrows the output distribution.

**Practical (80 min)** — Build the SFT dataset for the triage hop from your trace history.
Filter aggressively: keep only examples where the final investigation was correct *and* the
triage decision was verified right. Deduplicate by semantic similarity. Check class balance.
Hold out a test split that is never touched.

**Proof of understanding** — Report your dataset size after filtering versus before. The drop
is usually severe — 60–80% — and the filtered set is what makes the difference. Report class
distribution and confirm no category is under-represented to the point of being unlearnable.

**Reference** — "LIMA: Less Is More for Alignment."

---

### Day 147 — SFT and LoRA/QLoRA mechanics
**Concept (40 min)** — Full fine-tuning updates every weight and requires optimiser state
several times the model size in memory. **LoRA** freezes the base model and trains low-rank
update matrices, cutting trainable parameters by orders of magnitude with minimal quality
loss for narrow tasks. **QLoRA** additionally quantizes the frozen base, making single-GPU
tuning of substantial models practical. The adapter is small enough to swap at serving time,
which is what makes multi-task serving viable.

**Practical (80 min)** — LoRA-tune a small model on the triage dataset. Understand each
choice as you make it: rank, alpha, which modules get adapters, learning rate, epochs.
Instrument training and validation loss. Do not tune hyperparameters yet — get one clean run.

**Proof of understanding** — Report the trainable parameter count as a percentage of total,
and the peak VRAM used. Then state whether your validation loss curve shows overfitting, and
at which epoch — that determines tomorrow's search.

**Reference** — "LoRA: Low-Rank Adaptation of Large Language Models"; "QLoRA: Efficient
Finetuning of Quantized LLMs."

---

### Day 148 — The hyperparameters that actually matter
**Concept (40 min)** — Most fine-tuning hyperparameters barely matter; a few dominate. Rank
controls capacity (higher is not better — it overfits small datasets). Learning rate matters
enormously and is the most common cause of a failed run. Epochs on a small dataset overfit
fast. Which modules receive adapters matters more than rank. Systematic small sweeps beat
intuition, and you should be able to afford them at this scale.

**Practical (80 min)** — Sweep rank × learning rate × epochs on a small grid. Evaluate every
run on the held-out split *and* on your Phase 4 replay suite — validation loss and downstream
task performance frequently disagree, and the second one is what you care about.

**Proof of understanding** — Show a run where validation loss improved and replay-suite
performance got worse. This dissociation is why loss curves are not sufficient evidence, and
finding it yourself is the point of the day.

**Reference** — Your Day 101 replay suite.

---

### Day 149 — **[BUILD]** The distilled triage model
**Concept (40 min)** — Distillation as a framing: your frontier model is the teacher, its
verified outputs are the labels, and a small model is the student learning to imitate it on a
narrow task. The student does not need general capability, only this one behaviour.

**Practical (80 min)** — Train the final triage model with your best hyperparameters. Evaluate
against three baselines on the replay suite: the frontier model, the un-tuned small model,
and the un-tuned self-hosted mid-tier model. Measure accuracy, latency and cost per call.

**Proof of understanding** — Report all four options on a cost-versus-accuracy plot. State
your choice and the reasoning. If the un-tuned mid-tier model matches your distilled model,
the fine-tuning was not worth it — say so, and that is a genuinely valuable finding.

**Reference** — "Distilling Step-by-Step"; your Day 43 model comparison methodology.

---

### Day 150 — **[CONSOLIDATE]** What fine-tuning bought
**Concept (40 min)** — Account for the *total* cost of the fine-tune: data preparation time,
training compute, evaluation time, and the ongoing burden of versioning, monitoring and
re-training a model you now own. Compare against the per-call saving.

**Practical (80 min)** — Compute the payback period: hours invested plus training cost,
divided by savings per incident, times incident rate. Write `notes/day-150.md`. Spaced review:
Days 128 and 145.

**Proof of understanding** — State the payback period in months. If SENTINEL handles 50
incidents a day, the arithmetic works out very differently than at 5 a day. This is the
calculation that should precede every fine-tuning project and almost never does.

**Reference** — Your `costs.jsonl`.

---

## Week 26 — Preferences, embeddings, and honest evaluation

### Day 151 — Preference tuning: DPO and ORPO
**Concept (40 min)** — SFT teaches a model to imitate good outputs. Preference tuning teaches
it to prefer better outputs over worse ones, using pairs. **DPO** optimises the preference
objective directly without a separate reward model, which makes it far more practical than
RLHF at small scale. **ORPO** folds preference optimisation into SFT in one stage. Preference
tuning is the right tool when quality is a matter of degree rather than correctness — style,
verbosity, calibration, hedging.

**Practical (80 min)** — Build a small preference dataset for SENTINEL's report generation
from your Phase 4 human feedback: reports that were approved versus reports that were edited
before approval. Run DPO on a small model. Evaluate on report-quality judges and on human
preference.

**Proof of understanding** — Report the win rate of the DPO model against the SFT model on
held-out pairs. Then check calibration (Day 90) — preference tuning on human approvals often
makes a model *more* confident, which may worsen your false confidence rate. Measure it.

**Reference** — "Direct Preference Optimization"; "ORPO: Monolithic Preference Optimization
without Reference Model."

---

### Day 152 — Distillation for the harder hops
**Concept (40 min)** — The triage hop was easy — classification with abundant labels. Harder
hops (hypothesis formation) need reasoning distillation: the teacher produces reasoning traces
as well as answers, and the student learns the reasoning pattern, not just the mapping.
Success is much more variable here, and knowing where distillation stops working is as
valuable as knowing where it works.

**Practical (80 min)** — Attempt reasoning distillation on hypothesis formation: generate
teacher traces on corpus incidents, filter to verified-correct investigations, and tune a
mid-size model. Evaluate on the replay suite against the frontier model.

**Proof of understanding** — Report the gap between the distilled student and the teacher on
hypothesis formation, and compare that gap to the triage gap. It will be much larger. State
the task property that predicts distillation difficulty — that generalisation is the real
takeaway.

**Reference** — "Distilling the Knowledge in a Neural Network"; "Orca: Progressive Learning
from Complex Explanation Traces."

---

### Day 153 — Fine-tuning embeddings and rerankers
**Concept (40 min)** — Often the highest-return adaptation in a RAG system, and consistently
overlooked in favour of tuning the generator. A domain-tuned embedding model learns that your
error codes, service names and log formats are meaningful, which a general model cannot know.
Training uses contrastive pairs — and you built exactly that dataset on Day 38.

**Practical (80 min)** — Fine-tune an embedding model on your retrieval eval set using
contrastive learning with hard negatives (documents that are topically similar but wrong —
the Day 7 adversarial cases). Evaluate recall@5 against the base model. Then fine-tune the
cross-encoder reranker similarly.

**Proof of understanding** — Report recall@5 lift for the tuned embedding model and nDCG lift
for the tuned reranker. Compare these lifts against what you gained from tuning the generator.
For most RAG systems the retrieval-side tuning wins, and the field spends its attention on
the wrong half.

**Reference** — "Sentence-BERT"; "SimCSE"; your Day 38 eval set.

---

### Day 154 — Evaluating a fine-tune honestly
**Concept (40 min)** — Fine-tuned models fail in ways benchmarks hide. **Catastrophic
forgetting** — the model gets better at your task and worse at everything adjacent, which
matters because agents need general capability at the edges. **Narrowed output distribution**
— it now only produces outputs resembling your training data and handles novel inputs badly.
**Overfitting to your corpus** — it learns the specific quirks of your synthetic incidents
rather than incident reasoning. **Silent degradation** on inputs outside the training
distribution.

**Practical (80 min)** — Test all four. Run a general capability check on the tuned model to
detect forgetting. Construct 15 out-of-distribution incidents unlike anything in training and
compare tuned versus base performance. Measure output diversity.

**Proof of understanding** — Report tuned-versus-base performance on out-of-distribution
incidents. If the tuned model is worse there, you have traded robustness for in-distribution
accuracy — and for incident response, where novel failures are the interesting ones, that
trade may be unacceptable. Make the call explicitly.

**Reference** — "Catastrophic Forgetting in Neural Networks"; your Day 98 corpus distribution
analysis.

---

### Day 155 — **[BUILD]** SENTINEL v0.6 with adapter serving
**Concept (40 min)** — Serving fine-tuned models: LoRA adapters can be hot-swapped on a shared
base model, so multiple tuned behaviours run on one GPU without loading multiple full models.
This is what makes per-task tuning economically viable rather than a per-model GPU cost.

**Practical (80 min)** — Deploy the base model with your adapters via vLLM's multi-LoRA
support. Route the triage hop to the tuned adapter, retrieval to the tuned embedding model,
and reranking to the tuned reranker. Run the full replay suite and a load test. Tag `v0.6`.

**Proof of understanding** — Report cost per incident and quality for v0.6 versus v0.5, plus
the serving overhead of adapter swapping under concurrent load. If swapping overhead exceeds
the savings at your concurrency, dedicate a GPU or drop the adapter — measure, then decide.

**Reference** — vLLM multi-LoRA documentation.

---

### Day 156 — **[CONSOLIDATE]** Phase 6 review + publish
**Concept (40 min)** — The thesis: fine-tuning is a narrow tool with a real total cost of
ownership; the highest-return adaptation in most RAG-based agent systems is on the retrieval
side, not the generator; and the payback calculation should gate the decision.

**Practical (80 min)** — Draft deliverable #7: **"Distilling your agent's hot path."** Lead
with the Day 145 decision tree and the Day 150 payback arithmetic. Include the Day 148
loss-versus-task dissociation, the Day 153 retrieval-tuning comparison, and the Day 154
out-of-distribution result. Spaced review: Days 145 and 153.

**Proof of understanding** — A reader can decide whether *their* system should fine-tune,
using your decision tree and payback formula, before writing any training code.

**Reference** — Your `notes/` from Days 145–155.

---

## Phase 6 exit checklist

- [ ] Every SENTINEL step audited against the fine-tuning decision tree, with rejections noted
- [ ] Curated SFT dataset with the filtering drop-rate reported
- [ ] A LoRA run you understand parameter-by-parameter
- [ ] A demonstrated case where validation loss and task performance disagree
- [ ] Distilled triage model compared against three baselines on cost and accuracy
- [ ] Payback period computed in months
- [ ] Preference tuning attempted, with its effect on calibration measured
- [ ] Reasoning distillation attempted on a hard hop; the difficulty gap explained
- [ ] Embedding and reranker fine-tuned; lift compared against generator-side tuning
- [ ] Out-of-distribution robustness of the tuned model measured
- [ ] Multi-LoRA adapter serving working, with swap overhead measured
- [ ] SENTINEL v0.6 tagged
- [ ] Phase deliverable #7 drafted

**Next:** [Phase 7 — AI System Design & Security](phase-07-system-design-security.md)

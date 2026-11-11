# Phase 4 — Evaluation, Observability & Reliability
**Days 97–120 · 4 weeks**

You have been evaluating retrieval since Day 37 and orchestration since Day 72. This phase
makes evaluation the *spine* of the system rather than a thing you do afterwards, and adds
the production discipline — tracing, SLOs, guardrails, drift — that separates a working
prototype from something you would page someone about.

Your bio names evaluation as one of the hard parts. This is where that claim becomes a
suite of numbers with a CI gate behind them.

**Phase deliverable:** *Eval-driven agent development.*
**Capstone milestone:** SENTINEL v0.4 — 150-case replay suite, CI gate, full OTel tracing,
cost dashboard, guardrails, SLOs.

---

## Week 17 — The evaluation spine

### Day 97 — Eval-driven development for agents
**Concept (40 min)** — The discipline: before changing anything, you must be able to state
which metric it should move and by how much. This inverts the normal agent workflow, where
people change a prompt, eyeball three outputs, and ship. Agents make this worse than
ordinary software because the feedback signal is noisy — you genuinely cannot tell whether
a change helped from five examples, and human intuition about LLM output quality is
unreliable at exactly the scale people rely on it.

**Practical (80 min)** — Write `sentinel/evals/METHODOLOGY.md`: your eval philosophy, the
metrics you track, what counts as a regression, what change requires an eval run, and the
minimum sample size for a claim. Then audit your own last 20 commits — how many changed
behaviour without an eval run? Be honest; the number is usually embarrassing.

**Proof of understanding** — Adopt a rule for the remaining 83 days: no behaviour-changing
commit without a before/after number in the commit message. Write it into the methodology
doc.

**Reference** — Your `notes/` from Phase 3, where you will find several unmeasured changes.

---

### Day 98 — Building golden datasets from traces
**Concept (40 min)** — Your best eval data comes from real runs, not from imagination. The
workflow: capture traces, sample strategically (not uniformly — oversample failures and
edge cases), label them, and promote them into the golden set. The trap is distribution
drift between your golden set and reality; the other trap is a golden set that only contains
cases your system already handles.

**Practical (80 min)** — Build the trace-to-golden-case pipeline. Sample from your corpus
runs: all failures, a stratified sample of successes, and every case where confidence and
correctness disagreed. Expand the corpus toward 150 cases, prioritising categories where
you currently have thin coverage.

**Proof of understanding** — Report your corpus class distribution and compare it against
your best estimate of real-world incident distribution. Where they differ, say whether it is
deliberate (oversampling hard cases) or accidental (you only built what was easy).

**Reference** — Your Day 42 and Day 24 failure classifications.

---

### Day 99 — Metric design: success, faithfulness, groundedness
**Concept (40 min)** — Different questions need different metrics. **Task success** — did it
get the right answer. **Faithfulness** — is the output consistent with the retrieved
evidence. **Groundedness** — is every claim traceable to a source. **Attribution** — are the
citations correct. An agent can be right and unfaithful (correct answer, invented reasoning)
which is the most dangerous combination, because it passes outcome evaluation while being
untrustworthy.

**Practical (80 min)** — Implement faithfulness and groundedness scoring for SENTINEL:
decompose each report into atomic claims and check each against the evidence set. Run across
the corpus. Cross-tabulate correctness against faithfulness.

**Proof of understanding** — Report the count of correct-but-unfaithful reports. Every one is
a case where SENTINEL got lucky and would not have generalised. This number is invisible to
accuracy metrics and is the reason faithfulness exists.

**Reference** — "RAGAS: Automated Evaluation of Retrieval Augmented Generation";
"SelfCheckGPT."

---

### Day 100 — Tool-call accuracy and trajectory evaluation
**Concept (40 min)** — Outcome evaluation asks whether the final answer was right. Trajectory
evaluation asks whether the *path* was right — did it call the correct tools with the correct
arguments in a sensible order, and did it surface the minimal evidence set? Trajectory
evaluation catches agents that reach the right answer by luck, and it is why you wrote
minimal evidence sets on Day 17.

**Practical (80 min)** — Implement trajectory metrics: tool-call precision and recall against
the expected tool set, argument accuracy, evidence recall against the minimal evidence set,
and redundant-call rate. Run across the corpus.

**Proof of understanding** — Find a case with correct outcome and poor trajectory — right
answer, wrong path. Then find the inverse: good trajectory, wrong conclusion. The first is
fragile; the second is a reasoning problem. Different fixes, and only trajectory evaluation
distinguishes them.

**Reference** — Your Day 17 minimal evidence sets.

---

### Day 101 — **[BUILD]** The replay evaluation suite
**Concept (40 min)** — Make the full evaluation a single command that runs the entire corpus
and reports every metric. If it is slow or awkward, you will avoid it, and the whole phase
is wasted.

**Practical (80 min)** — Build `sentinel/evals/replay.py`: runs all corpus cases (parallel,
rate-limited), computes all eight success metrics plus faithfulness, groundedness and
trajectory metrics, writes a versioned result file, and diffs against the previous run with
per-case regression detection.

**Proof of understanding** — Full suite runs in under 15 minutes and costs a known,
acceptable amount. Report both numbers. If a full eval costs $40, you will run it weekly —
so either cut the cost or accept a slower feedback loop deliberately.

**Reference** — Your Day 41 retrieval harness, extended to full system evaluation.

---

### Day 102 — **[CONSOLIDATE]** The evaluation dashboard
**Concept (40 min)** — Metrics you cannot see are metrics you will not act on. Build the view
that tells you the system's state in ten seconds.

**Practical (80 min)** — Build a dashboard in the Next.js console: all metrics over time by
version tag, per-case drill-down, and a regression list. Spaced review: Days 37 and 90.

**Proof of understanding** — From the dashboard alone, answer: which version was best on
false confidence rate, and what changed in the version where accuracy dropped? If you cannot,
the dashboard is decoration.

**Reference** — `sentinel/CHANGELOG.md`.

---

## Week 18 — Judges and assertions

### Day 103 — LLM-as-judge: rubric design
**Concept (40 min)** — Many qualities cannot be checked programmatically — is this root-cause
explanation clear, is this evidence sufficient, is this remediation sensible. LLM judges fill
that gap. Rubric design decides whether they work: specific criteria beat "rate 1–10,"
reference-based grading beats reference-free, binary or few-point scales beat fine-grained
ones, and requiring the judge to cite evidence before scoring materially improves agreement.

**Practical (80 min)** — Write judge rubrics for three SENTINEL qualities: evidence
sufficiency, explanation clarity, and remediation appropriateness. Each with explicit
criteria, a 3-point scale with anchor descriptions, and a required citation. Run across 40
corpus cases.

**Proof of understanding** — Report the score distribution per rubric. A judge that gives 90%
of cases the same score has no discriminative power and is telling you nothing — fix the
rubric, not the system.

**Reference** — "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena."

---

### Day 104 — Judge failure modes
**Concept (40 min)** — Judges have systematic, well-documented biases: **position bias**
(favouring the first or second option in pairwise comparison), **verbosity bias** (longer
answers score higher regardless of quality), **self-enhancement bias** (models prefer output
from their own family), and poor calibration at the extremes. Every one of these is
measurable and most are partially correctable.

**Practical (80 min)** — Measure each bias in your own judge. Position: run pairwise
comparisons in both orders and count disagreements. Verbosity: pad a correct answer with
irrelevant-but-plausible text and see if the score rises. Self-enhancement: judge output from
two model families with a judge from one of them.

**Proof of understanding** — Report your position-bias disagreement rate. If swapping the
order changes the verdict in 15% of cases, every pairwise result you produce must be
order-randomised or run in both directions. State the mitigation you adopted.

**Reference** — "Large Language Models are not Fair Evaluators"; "Judging LLM-as-a-Judge."

---

### Day 105 — Evaluating the judge
**Concept (40 min)** — A judge is a measurement instrument and an uncalibrated instrument
produces confident nonsense. You validate it the way you validate any classifier: against
human labels, reported as agreement (Cohen's kappa, not raw accuracy — raw agreement is
inflated by class imbalance).

**Practical (80 min)** — Hand-label 60 cases yourself against your rubrics. Compute Cohen's
kappa between you and the judge per rubric. For every disagreement, decide whether you or the
judge was right — and note when the judge was right, because that happens and it is
informative.

**Proof of understanding** — Report kappa per rubric. Below ~0.6 the judge is not usable for
that rubric and you must either fix the rubric or drop the metric. Say which of yours
survived.

**Reference** — Cohen's kappa; inter-annotator agreement methodology.

---

### Day 106 — Deterministic assertions and agent unit tests
**Concept (40 min)** — Not everything needs a model. Many important properties are
programmatically checkable and should be: every claimed service name exists, every cited log
line appears in the evidence, timestamps fall inside the incident window, the report contains
a remediation section, no mutating tool was called without an approval event. These run in
milliseconds, cost nothing, and never drift. Use them everywhere you can and reserve the
judge for what genuinely needs judgment.

**Practical (80 min)** — Write 25 deterministic assertions over SENTINEL's output and
trajectory. Run across the corpus. Anywhere a judge and an assertion can measure the same
thing, delete the judge.

**Proof of understanding** — Report how many of your assertions fail somewhere in the corpus.
Assertions that never fail are either trivially true or wrong — audit them.

**Reference** — Property-based testing principles; your Day 21 validation layer.

---

### Day 107 — **[BUILD]** Judges and assertions in the suite
**Concept (40 min)** — Integrate: assertions run first (fast, free, deterministic), judges run
only on cases that pass assertions, human review is reserved for judge-uncertain cases. A
tiered evaluation pyramid.

**Practical (80 min)** — Wire the tiers into `replay.py`. Report cost and time per tier.
Ensure a full run still fits your Day 101 budget — judges are expensive and it is easy to
triple your eval cost here.

**Proof of understanding** — Report the cost breakdown per tier. If judges are over 70% of
eval cost, push more checks down into assertions.

**Reference** — Your Day 101 eval cost baseline.

---

### Day 108 — **[CONSOLIDATE]** Metric review
**Concept (40 min)** — You now have many metrics. Too many metrics is the same problem as
none — nobody knows which one to optimise. Pick the small set that decides whether you ship.

**Practical (80 min)** — Choose three primary metrics and demote the rest to diagnostic.
Document the choice and the reasoning in `METHODOLOGY.md`. Spaced review: Days 99 and 104.

**Proof of understanding** — Defend your three. For SENTINEL, a strong case exists for
root-cause accuracy@3, false confidence rate, and cost per incident — but make your own
argument.

**Reference** — `sentinel/SPEC.md`.

---

## Week 19 — Rigor, CI, and tracing

### Day 109 — Statistical rigor
**Concept (40 min)** — Agent outputs are stochastic (Day 3), so a single run is a sample, not
a measurement. Two prompts differing by 3 points on 20 cases are indistinguishable from noise.
You need: repeated runs to estimate variance, sample sizes derived from the effect size you
care about, paired comparison (same cases, both configurations) which is far more powerful
than independent comparison, and awareness that testing 10 variants against one eval set will
produce a "winner" by chance.

**Practical (80 min)** — Run your current configuration 5 times over the corpus and compute
per-metric standard deviation. Use that to compute the minimum detectable effect at n=150.
Implement paired comparison in `replay.py`.

**Proof of understanding** — State your minimum detectable effect for root-cause accuracy.
If it is 6 points, then every 3-point "improvement" in your notes from Phases 2 and 3 was
noise. Go back and mark them.

**Reference** — Paired statistical testing; "The Multiple Comparisons Problem."

---

### Day 110 — Regression suites and gating CI
**Concept (40 min)** — Evaluation that runs when you remember is evaluation that stops
running. CI gating makes it structural. The design questions: what runs on every commit (fast
assertions, a 20-case smoke suite) versus nightly (the full 150-case suite with judges), what
constitutes a blocking failure versus a warning, and how you avoid the eval suite becoming
so flaky that people disable it.

**Practical (80 min)** — Set up CI: on every commit, run assertions plus a 20-case smoke
suite, blocking on any assertion failure or a smoke accuracy drop beyond your Day 109 noise
floor. Nightly, run the full suite and post results. Make a deliberately bad change and
confirm CI catches it.

**Proof of understanding** — Show CI blocking a real regression. Then report the smoke
suite's false-positive rate over 10 runs of *unchanged* code — if it fails on unchanged code,
your threshold is inside the noise band.

**Reference** — Your Day 109 variance measurements.

---

### Day 111 — Tracing with OpenTelemetry
**Concept (40 min)** — Agent systems are distributed systems and need distributed tracing.
Span design matters: one span per model call with model, token counts and latency; one per
tool call with arguments and result size; one per orchestration node; and a root span per
investigation. Correct parent-child relationships across your parallel branches are what make
the trace readable.

**Practical (80 min)** — Instrument SENTINEL fully with OTel. Get parent-child relationships
right across fan-out. Add semantic attributes for model, tokens, cost, and tool name. View
real traces and find something you did not know about your own system.

**Proof of understanding** — Name one thing the trace revealed that you did not know — a
redundant call, an unexpectedly slow tool, a step running serially that you believed was
parallel. There is always something.

**Reference** — OpenTelemetry semantic conventions for GenAI.

---

### Day 112 — Cost and latency attribution
**Concept (40 min)** — "This costs $0.42 per incident" is not actionable. "Hypothesis fan-out
is 61% of cost, and 80% of that is re-sending retrieved evidence to every branch" is
actionable. Attribution means every dollar and every millisecond is assigned to a component
you could change.

**Practical (80 min)** — Add cost as a span attribute computed from token counts and model
rates. Build attribution rollups: cost by orchestration node, by model, by tool, by
retrieval source. Same for latency, including time spent waiting on rate limits.

**Proof of understanding** — Report your top three cost centres and top three latency
centres as percentages. Then name the single change that would cut the most cost — this
becomes Phase 5's first target.

**Reference** — Your Day 84 latency breakdown, now automated.

---

### Day 113 — **[BUILD]** CI gate and cost dashboard
**Concept (40 min)** — Make the numbers unavoidable — visible on every commit and every day.

**Practical (80 min)** — Finish the CI gate and add cost tracking to it: a commit that raises
cost per incident by more than 15% fails CI unless explicitly acknowledged in the commit
message. Extend the dashboard with cost and latency attribution views.

**Proof of understanding** — Cost regressions now fail CI. Demonstrate it with a deliberately
wasteful change. Cost regressions ship silently in almost every LLM product; yours cannot.

**Reference** — Your `costs.jsonl`, now nine weeks deep.

---

### Day 114 — **[CONSOLIDATE]** Reading the system through its traces
**Concept (40 min)** — With full tracing, re-examine everything you concluded in Phases 2 and
3 using better instrumentation than you had at the time.

**Practical (80 min)** — Pick five conclusions from earlier phases and verify them against
trace data. Spaced review: Days 48 and 84.

**Proof of understanding** — Find at least one earlier conclusion the traces contradict. You
were measuring with cruder instruments then; correct the record in `notes/`.

**Reference** — Your Phase 2 and 3 notes.

---

## Week 20 — Production reliability

### Day 115 — Online evaluation and implicit feedback
**Concept (40 min)** — Offline evaluation uses a fixed corpus that ages. Online evaluation
measures the live system, mostly through implicit signals: did the human approve the proposed
remediation, did they edit it first, did they abandon the investigation, how long until they
overrode it. These are noisier than labels and far more honest about real value.

**Practical (80 min)** — Instrument implicit signals in the console: approval rate, edit rate,
abandonment rate, time to human decision. Add a lightweight explicit feedback control. Build
the pipeline that promotes low-approval cases into the golden set.

**Proof of understanding** — Name which implicit signal best predicts a case your offline
metrics scored well but a human rejected. That signal is your early warning system.

**Reference** — Your Day 98 golden dataset pipeline.

---

### Day 116 — Drift detection
**Concept (40 min)** — Agent systems degrade silently. Causes: the model provider updates the
model underneath you, your corpus ages relative to reality, retrieved documents change,
usage patterns shift. Nothing errors — quality just erodes. Detection requires a stable
canary set run on a schedule and monitored for statistically significant movement.

**Practical (80 min)** — Build a canary suite: 25 stable cases run daily, results tracked over
time with control limits derived from your Day 109 variance. Alert on out-of-band movement.
Simulate drift by swapping model versions and confirm detection.

**Proof of understanding** — Report the smallest quality drop your canary detects within one
day. If it only catches catastrophic failures, add cases or tighten the limits.

**Reference** — Statistical process control; your variance measurements.

---

### Day 117 — Guardrails
**Concept (40 min)** — Input and output filtering as a distinct layer: PII detection and
redaction (logs are full of it), prompt-injection detection on retrieved content, output
checks for leaked secrets, and refusal handling when the model declines a legitimate request.
Guardrails have false positives, and an over-aggressive guardrail during an outage is its own
incident.

**Practical (80 min)** — Implement input guardrails (PII redaction on ingested logs,
injection detection on retrieved content) and output guardrails (secret detection, required
disclaimer when confidence is low). Measure false-positive rate on the corpus.

**Proof of understanding** — Report guardrail false-positive rate. Then find a legitimate
incident your guardrails would have blocked. Every guardrail has one; knowing yours is the
difference between a safety layer and an availability problem.

**Reference** — OWASP Top 10 for LLM Applications; Microsoft Presidio for PII patterns.

---

### Day 118 — SLOs, fallbacks and circuit breakers
**Concept (40 min)** — Standard reliability engineering, applied to a stochastic system. SLOs
for agents need care: availability is easy, but "quality" as an SLO requires the online
metrics from Day 115. Fallbacks: if the frontier model is down, degrade to local; if retrieval
fails, proceed with reduced confidence and say so. Circuit breakers prevent a failing
dependency from consuming your entire budget in retries.

**Practical (80 min)** — Define SLOs for SENTINEL: availability, p95 time to hypothesis, and
a quality floor. Implement fallback chains for model unavailability and retrieval failure.
Implement circuit breakers on every external dependency. Test by taking each dependency down.

**Proof of understanding** — Take your primary model provider offline (block it at the
network level) and show SENTINEL producing a degraded but useful result on local models.
Report the accuracy in degraded mode — that number is your real floor.

**Reference** — "Site Reliability Engineering" (Google), SLO chapters; "Release It!"
(circuit breaker pattern).

---

### Day 119 — **[BUILD]** SENTINEL v0.4
**Concept (40 min)** — Integration. v0.4 = 150-case replay suite + tiered evaluation + CI
gating on quality and cost + full OTel tracing with attribution + online feedback + drift
canary + guardrails + SLOs with fallbacks and circuit breakers.

**Practical (80 min)** — Assemble, run the full suite, tag `v0.4`, update the changelog with
every metric plus your newly-measurable ones.

**Proof of understanding** — v0.4 versus v0.3 across all metrics, with confidence intervals
now that you know your variance. Any improvement you claim must exceed your minimum
detectable effect.

**Reference** — `sentinel/CHANGELOG.md`.

---

### Day 120 — **[CONSOLIDATE]** Phase 4 review + publish
**Concept (40 min)** — The thesis: agent development without evaluation is guessing with extra
steps, most reported improvements in this field are inside the noise band, and the judge you
are trusting has never been validated.

**Practical (80 min)** — Draft deliverable #5: **"Eval-driven agent development."** Lead with
the Day 109 minimum detectable effect and how many of your own earlier "improvements" it
invalidated — that is the most honest and most useful thing in the post. Include the Day 105
judge kappa and the Day 104 position-bias number. Spaced review: Days 97 and 109.

**Proof of understanding** — The post gives a reader a checklist for building an eval suite
that would survive scrutiny, grounded in your own numbers.

**Reference** — Your `notes/` from Days 97–119.

---

## Phase 4 exit checklist

- [ ] 150-case corpus with class distribution documented and justified
- [ ] Full replay suite runs in under 15 minutes at a known cost
- [ ] Faithfulness and groundedness measured; correct-but-unfaithful count known
- [ ] Trajectory evaluation against minimal evidence sets
- [ ] Judge validated against your own labels — kappa reported per rubric
- [ ] Judge position bias, verbosity bias and self-enhancement bias measured
- [ ] 25+ deterministic assertions running before any judge
- [ ] Variance measured; minimum detectable effect known and applied retroactively
- [ ] CI gates on quality regression *and* cost regression
- [ ] Full OTel tracing with cost and latency attribution by component
- [ ] Drift canary running daily with control limits
- [ ] Guardrails with a measured false-positive rate
- [ ] SLOs, fallback chains and circuit breakers, tested by taking dependencies down
- [ ] SENTINEL v0.4 tagged
- [ ] Phase deliverable #5 drafted

**Next:** [Phase 5 — Serving, Inference & Cost Engineering](phase-05-serving-inference-cost.md)
